import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
import pandas as pd


SELECTORS = {
    "title":           ("[data-test='job-title']", None),
    "salary_estimate": ("[data-test='detailSalary']", None),
    "company_name":    (".EmployerProfile_compactEmployerName__9MGcV", None),
    "rating":          (".rating-single-star_RatingSingleStarContainer__JbmtR", "aria-valuenow"),
    "location":        ("[data-test='emp-location']", None),
    "description":     ("[data-test='descSnippet']", None),
}


def safe_find(card, selector, attribute=None):
    try:
        element = card.find_element(By.CSS_SELECTOR, selector)
        return element.get_attribute(attribute) if attribute else element.text.strip()
    except NoSuchElementException:
        return "N/A"


def scrape_card(card):
    return {key: safe_find(card, sel, attr) for key, (sel, attr) in SELECTORS.items()}


def get_jobs(keyword, num_jobs, path, slp_time):
    driver = webdriver.Chrome()

    keyword_formatted = keyword.lower().replace(" ", "-")
    url = f"https://www.glassdoor.com/Job/{keyword_formatted}-jobs-SRCH_KO0,{len(keyword)}.htm"
    driver.get(url)

    jobs = []

    while len(jobs) < num_jobs:
        WebDriverWait(driver, slp_time).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-test='jobListing']"))
        )

        job_cards = driver.find_elements(By.CSS_SELECTOR, "[data-test='jobListing']")

        for card in job_cards:
            if len(jobs) >= num_jobs:
                break

            job = scrape_card(card)
            jobs.append(job)
            print(f"Scraped job {len(jobs)}: {job['title']} at {job['company_name']} | salary: {job['salary_estimate']}")

        if len(jobs) >= num_jobs:
            break

    driver.quit()
    return pd.DataFrame(jobs)