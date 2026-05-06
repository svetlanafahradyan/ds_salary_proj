import glassdoor_scraper as gs
import pandas as pd

path = "/opt/homebrew/bin/chromedriver"
df = gs.get_jobs('data scientist', 1000, path, 15)

df.to_csv("jobs.csv", index=False)