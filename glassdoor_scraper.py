"""
glassdoor_scraper.py
--------------------
Scrapes job listings from Glassdoor using Selenium (Chrome).

Usage:
    df = get_jobs(keyword="data scientist", num_jobs=50, path="jobs.csv", sleep_time=10)

Dependencies:
    selenium, pandas, chromedriver (must match installed Chrome version)

Notes:
    - CSS selectors in SELECTORS are tied to Glassdoor's current DOM — verify after any
      site redesign.
    - The auth modal interceptor must run AFTER the load-more click, not before,
      because Glassdoor only triggers the login wall after user interaction.
"""


import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException


def setup(keyword):
    """
    Initialise a Chrome WebDriver and navigate to the Glassdoor job search page.

    Glassdoor's job search URL encodes the keyword length as part of the path,
    e.g. "data-scientist-jobs-SRCH_KO0,14.htm" for a 14-character keyword.
    Spaces are replaced with hyphens to match Glassdoor's slug format.

    Args:
        keyword: Raw job title / search term (e.g. "data scientist").

    Returns:
        A live Chrome WebDriver instance pointed at the search results page.
    """
    driver = webdriver.Chrome()
    keyword_formatted = keyword.lower().replace(" ", "-")
    url = f"https://www.glassdoor.com/Job/{keyword_formatted}-jobs-SRCH_KO0,{len(keyword)}.htm"
    driver.get(url)
    return driver


def teardown(driver):
    """
    Close the browser and release the WebDriver session.

    Args:
        driver: The active Chrome WebDriver instance to close.
    """
    driver.quit()


# ---------------------------------------------------------------------------
# CSS selector registry
# ---------------------------------------------------------------------------
# Centralised here so any Glassdoor DOM change only requires one edit.
# Keys map 1-to-1 with the columns produced by scrape_card().
# "rating" is intentionally excluded from the standard text-extraction loop
# because its value lives in an aria attribute, not in element.text.
# ---------------------------------------------------------------------------
SELECTORS = {
    "title":           "[data-test='job-title']",
    "salary_estimate": "[data-test='detailSalary']",
    "company_name":    ".EmployerProfile_compactEmployerName__9MGcV",
    "rating":          ".rating-single-star_RatingSingleStarContainer__JbmtR",
    "location":        "[data-test='emp-location']",
    "description":     "[data-test='descSnippet']",
}


def safe_find(card, selector, attribute=None):
    """
    Attempt to locate a child element within a job card and return its value.

    Returns "N/A" instead of raising, so a single missing field never aborts
    the entire scrape. This is intentional: Glassdoor omits salary, rating,
    etc. on a significant proportion of listings.

    Args:
        card:      The parent Selenium WebElement (a job listing card).
        selector:  CSS selector string targeting the desired child element.
        attribute: If provided, return this HTML attribute's value instead of
                   the element's visible text (e.g. "aria-valuenow" for rating).

    Returns:
        The element's text (stripped) or attribute value; "N/A" if not found.
    """
    try:
        element = card.find_element(By.CSS_SELECTOR, selector)
        return element.get_attribute(attribute) if attribute else element.text.strip()
    except NoSuchElementException:
        return "N/A"



def scrape_card(card):
    """
    Extract all tracked fields from a single job listing card.

    All standard fields are extracted via a dict comprehension over SELECTORS.
    Rating is handled separately because its value is stored in the
    aria-valuenow attribute rather than the element's inner text.

    Args:
        card: A Selenium WebElement representing one job listing card.

    Returns:
        A flat dict with keys matching SELECTORS (title, salary_estimate,
        company_name, rating, location, description).
    """
    return {
        **{key: safe_find(card, sel) for key, sel in SELECTORS.items() if key != "rating"},
        "rating": safe_find(card, SELECTORS["rating"], "aria-valuenow"),
    }


def get_jobs(keyword, num_jobs, path, sleep_time):
    """
    Scrape up to `num_jobs` Glassdoor job listings for the given keyword.

    Pagination strategy
    -------------------
    Glassdoor uses an infinite-scroll / "Load more" button pattern rather than
    traditional page numbers. After each click we wait for the total card count
    to exceed the previous count before slicing out only the newly added cards.
    This avoids double-scraping cards that were already processed.

    Modal handling
    --------------
    Glassdoor injects a login/signup modal after user interactions (clicks).
    The modal interceptor runs AFTER the load-more click, matching the actual
    order in which Glassdoor triggers it. Running it before would be a no-op
    on the first iteration.

    Known limitations
    -----------------
    Glassdoor actively restricts automated scraping — the "Load more" button
    is frequently suppressed or rendered non-functional for bot-like sessions,
    meaning the scraper may return far fewer than `num_jobs` results even when
    more listings exist on the site. 

    Args:
        keyword:    Job title / search term (e.g. "data scientist").
        num_jobs:   Maximum number of job listings to collect.
        path:       File path for saving results (reserved for caller use;
                    not written inside this function).
        sleep_time: Maximum seconds WebDriverWait will poll for new cards
                    to appear after a "Load more" click.

    Returns:
        A pandas DataFrame where each row is one job listing and columns
        correspond to the keys in SELECTORS.
    """
    driver = setup(keyword)
    jobs = []
    previous_count = 0

    while len(jobs) < num_jobs:
        # Wait until we have MORE cards than the previous page
        WebDriverWait(driver, sleep_time).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "[data-test='jobListing']")) > previous_count
        )

        job_cards = driver.find_elements(By.CSS_SELECTOR, "[data-test='jobListing']")
        new_cards = job_cards[previous_count:]  # only the newly loaded ones
        previous_count = len(job_cards)


        # 1. Scrape current page
        for job_card in new_cards:
            if len(jobs) >= num_jobs:
                break
            job = scrape_card(job_card)
            jobs.append(job)
            print(f"Scraped job {len(jobs)}: {job['title']} at {job['company_name']} | salary: {job['salary_estimate']}")


        # 2. Paginate
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "[data-test='load-more']")
            print(f"Load more button found. Displayed: {btn.is_displayed()}, Enabled: {btn.is_enabled()}")
            btn.click()
            print("Clicked load more.")
        except NoSuchElementException:
            print("Load more button NOT FOUND in DOM.")
            break
        except ElementClickInterceptedException:
            print("Click intercepted — something is covering the button.")
            break


        # 3. Close modal if present
        try:
            driver.find_element(By.CSS_SELECTOR, "[data-test='auth-modal-close-button']").click()
        except NoSuchElementException:
            pass

    teardown(driver)
    return pd.DataFrame(jobs)