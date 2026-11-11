from playwright.sync_api import Playwright, sync_playwright, expect
from datetime import date, timedelta
customer_name = "{{store.BI_OTT}}"
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    username = page.get_by_role("textbox",name="Username Password")
    password = page.locator("#password")
    login_button = page.get_by_role("button",name="Login")
    project_management_button = page.get_by_role("button",name="Project Management")
    projects_tab = page.get_by_role("tab",name="Projects")
    self_assign_button = page.get_by_role("button",name="SELF ASSIGN SELF ASSIGN")
    proceed_button = page.get_by_role("button",name="Proceed")
    page.goto("{{env.pm}}")
    page.wait_for_timeout(5000)
    username.wait_for(state="visible",timeout=30000)
    username.fill("Karthick.R")
    password.fill("Hope@2026")
    login_button.click()
    page.wait_for_timeout(3000)
    project_management_button.wait_for(state="visible",timeout=30000)
    project_management_button.click()
    page.wait_for_timeout(3000)
    projects_tab.wait_for(state="visible",timeout=30000)
    projects_tab.click()
    page.get_by_role("tab", name="All Projects").click()
    page.wait_for_timeout(2000)
    
    # Locate the Customer name field
    customer_input = page.locator('input[name="Customer Name"]')
    customer_input.click()
    page.wait_for_timeout(2000)
    customer_input.fill(customer_name)
    search_icon = customer_input.locator("xpath=following-sibling::div//*[name()='svg' and contains(@class,'searchIcon')]")
    search_icon.click()
    
    page.wait_for_timeout(2000)
    page.locator("span[data-description='row-select']").first.click()
    page.wait_for_timeout(1000)
    self_assign_button.wait_for(state="visible",timeout=30000)
    self_assign_button.click()
    proceed_button.wait_for(state="visible",timeout=30000)
    proceed_button.click()
    page.wait_for_timeout(2000)
    print(f"Project self-assignment completed successfully for: {customer_name}")

    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)