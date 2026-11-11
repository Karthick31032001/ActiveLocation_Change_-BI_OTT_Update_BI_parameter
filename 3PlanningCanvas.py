from playwright.sync_api import Playwright, sync_playwright
from pathlib import Path
import calendar
from datetime import date, timedelta

customer_name = "{{store.BI_OTT}}"
# Compute once, reused everywhere a date needs to be selected
TARGET_DATE = date.today() + timedelta(days=4)
TARGET_DAY = TARGET_DATE.day
_MONTHS = {name: i for i, name in enumerate(calendar.month_name) if name}

def pick_date(page, target):
    """Move the open calendar to the right month and click the target day.
    Handles multiple MUI date picker variants by trying several
    known navigation-button patterns rather than assuming one class scheme."""

    def resolve_nav_button(direction):
        if direction == "next":
            candidates = [
                page.get_by_role("button", name="Next month"),
                page.get_by_role("button", name="Next Month"),
                page.locator('button[title="Next month"]'),
                page.locator('button[aria-label="Next month"]'),
                page.locator(".MuiPickersCalendarHeader-switchHeader button").last,
            ]
        else:
            candidates = [
                page.get_by_role("button", name="Previous month"),
                page.get_by_role("button", name="Previous Month"),
                page.locator('button[title="Previous month"]'),
                page.locator('button[aria-label="Previous month"]'),
                page.locator(".MuiPickersCalendarHeader-switchHeader button").first,
            ]
        for c in candidates:
            if c.count() > 0 and c.first.is_visible():
                return c.first
        raise Exception(f"Could not resolve '{direction}' calendar navigation button")

    def get_shown_month_year():
        # Try the older header text pattern first ("June 2026")
        old_header = page.locator(".MuiPickersCalendarHeader-transitionContainer")
        if old_header.count() > 0 and old_header.first.is_visible():
            shown = old_header.first.inner_text().strip()
            parts = shown.split()
            return int(parts[1]), _MONTHS[parts[0]]

        # Fall back to the newer header pattern (e.g. a label like "August 2026"
        # somewhere near the nav arrows)
        newer_header = page.locator("div:has-text('20')").filter(
            has=page.locator("button")
        ).last
        shown = newer_header.inner_text().strip()
        for word in shown.split():
            if word in _MONTHS:
                month_name = word
            if word.isdigit() and len(word) == 4:
                year = int(word)
        return year, _MONTHS[month_name]

    for _ in range(24):  # safety limit so it never loops forever
        page.wait_for_timeout(500)
        shown_year, shown_month = get_shown_month_year()

        if (shown_year, shown_month) == (target.year, target.month):
            break

        if (shown_year, shown_month) < (target.year, target.month):
            resolve_nav_button("next").click(timeout=30000)
        else:
            resolve_nav_button("previous").click(timeout=30000)

    # Select the target day, matching text and excluding disabled/outside-month cells
    day_str = str(target.day)
    candidates = page.get_by_text(day_str, exact=True)
    count = candidates.count()

    chosen = None
    for i in range(count):
        el = candidates.nth(i)
        clickable = el.locator(
            "xpath=ancestor-or-self::*[self::button or @role='button' or @role='gridcell'][1]"
        )
        if clickable.count() == 0:
            continue
        clickable = clickable.first
        class_attr = (clickable.get_attribute("class") or "").lower()
        aria_disabled = clickable.get_attribute("aria-disabled") or ""
        if "outside" in class_attr or "disabled" in class_attr or "hidden" in class_attr or aria_disabled == "true":
            continue
        chosen = clickable
        break

    if chosen is None and count > 0:
        chosen = candidates.first
    if chosen is None:
        raise Exception(f"Could not find a clickable day '{target.day}' in the calendar")

    chosen.wait_for(state="visible", timeout=30000)
    chosen.click(timeout=30000, force=True)

def pick_day(page, day):
    
    day_str = str(day)
    candidates = page.get_by_role("button", name=day_str, exact=True)

    if candidates.count() == 1:
        candidates.click(timeout=30000)
        return

    # Multiple matches -> exclude "outside month" padding days
    in_month = candidates.locator(":not(.MuiPickersDay-dayOutsideMonth)")
    if in_month.count() == 1:
        in_month.click(timeout=30000)
        return

    # Fallback: click the first enabled match
    in_month.locator(":not([disabled])").first.click(timeout=30000)

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
# Launching Browser _________________________________________________________________________
    page.goto("{{env.pm}}")
    page.get_by_role("textbox", name="Username Password").fill("Karthick.R")
    page.locator("#password").fill("Hope@2026")
    page.get_by_role("button", name="Login").click()
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="Project Management", exact=True).click()
    page.wait_for_timeout(3000)
    page.get_by_role("tab", name="Projects").click()
    page.wait_for_timeout(2000)
    page.get_by_role("tab", name="My Projects").click()
    page.get_by_role("row").filter(has_text=customer_name).locator("span.hyperlink").first.click()
    page.wait_for_timeout(4000)


    
### Planning Canvas & Subproject Creation ______________________________________________________________
    today = date.today()
    start_date = today + timedelta(days=4)
    end_date = today + timedelta(days=5)
   
    # Planned Start Date
    page.get_by_role("button", name="change date").first.click()
    pick_date(page, start_date)
    page.wait_for_timeout(2000)
    # Planned End Date
    page.get_by_role("button", name="change date").nth(1).click()
    pick_date(page, end_date)
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="SAVE").click()
    page.wait_for_timeout(4000)

    showFloatingIcon=page.get_by_role("button", name="Show Floating Icon")
    planningCanvas=page.get_by_role("menuitem", name="Planning Canvas Planning")

   
# 1. S2O Handoff Planning________________________________________________________________________
    s2oHandoffPlanning=page.locator("tr.MuiTableRow-root", has_text="S2O Handoff Planning").first.get_by_role("checkbox")
    byPass=page.get_by_role("button", name="Bypass Bypass")
    proceed=page.get_by_role("button", name="Proceed")
# 2. S2O Handoff Meeting_________________________________________________________________
    s2oHandoffMeeting=page.locator("tr.MuiTableRow-root", has_text="S2O Handoff Meeting").first.get_by_role("checkbox")
# 3. Customer Kick-Off________________________________________________________________________
    customerKickOff=page.locator("tr.MuiTableRow-root", has_text="Customer Kick-Off").first.get_by_role("checkbox")
# 4. Manage Solution Group_________________________________________________________________________
    manageSolutionGroup=page.locator("tr.MuiTableRow-root", has_text="Manage Solution Group").first.get_by_role("checkbox")
    refresh=page.get_by_role("button", name="Refresh Refresh")
 # Customer Data Gathering_______________________________________________________________
    # customerDataGathering=page.locator("tr.MuiTableRow-root", has_text="Customer Data Gathering").first.locator("span.hyperlink")
    ManageSolutionGroup=page.locator("tr.MuiTableRow-root", has_text="Manage Solution Group").first.locator("span.hyperlink")
    editTask=page.get_by_role("button", name="Edit task").first
    criticalDates=page.get_by_role("button", name="Critical Dates")
    customerDesiredDueDate=page.locator('div.MuiInputBase-root:has(input[name="Customer Desired Due Date"]) button')
    customerDesireSave=page.get_by_role("button", name="SAVE", exact=True).first
    close=page.get_by_role("button", name="close")
    complete=page.get_by_role("button", name="COMPLETE")
# Establish Site Rollout Groups________________________________________________________________
    group_name = "Site1"
    estabilishSiteRollout=page.get_by_text("Establish Site Rollout Groups")
    CustomerDataGathering=page.locator("//span[@class='stepperLabel'][text()='Customer Data Gathering']")
    add=page.locator(".MuiToolbar-root button[title='Add']")
    siteName=page.get_by_role("textbox", name="Site Rollout Group Name")
    siteSave=page.get_by_role("button", name="SAVE", exact=True)
    checkBox=page.locator("tr.MuiTableRow-root", has_text="47 13TH ST").first.get_by_role("checkbox")
    associate=page.get_by_role("button", name="ASSOCIATE", exact=True)
    associateclose=page.get_by_role("button", name="close", exact=True)
    grpCheckBox=page.locator("tr.MuiTableRow-root", has_text=group_name).first.get_by_role("checkbox")
    createSubProject=page.get_by_role("button", name="CREATE SUB PROJECT")




    showFloatingIcon.wait_for(state="visible",timeout=30000)
    showFloatingIcon.click()
    planningCanvas.click()
    page.wait_for_timeout(7000)

    s2oHandoffPlanning.wait_for(state="visible",timeout=30000)
    page.wait_for_timeout(2000)
    s2oHandoffPlanning.check()
    byPass.click()
    page.wait_for_timeout(1000)
    proceed.click()
    page.wait_for_timeout(2000)

    s2oHandoffMeeting.wait_for(state="visible",timeout=30000)
    page.wait_for_timeout(2000)
    s2oHandoffMeeting.check()
    byPass.click()
    page.wait_for_timeout(1000)
    proceed.click()
    page.wait_for_timeout(2000)

    customerKickOff.wait_for(state="visible",timeout=30000)
    page.wait_for_timeout(2000)
    customerKickOff.check(timeout=30000)
    byPass.click(timeout=30000)
    page.wait_for_timeout(1000)
    proceed.click(timeout=30000)
    page.wait_for_timeout(2000)

    manageSolutionGroup.wait_for(state="visible",timeout=30000)
    ManageSolutionGroup.click(timeout=30000)
    page.wait_for_timeout(2000)
    byPass.click(timeout=30000)
    page.wait_for_timeout(2000)
    proceed.click(timeout=30000)
    page.wait_for_timeout(4000)

    # CUSTOMER DATA GATHERING
    CustomerDataGathering.wait_for(state="visible", timeout=30000)
    CustomerDataGathering.click()
    page.wait_for_timeout(5000)
    
    processed_locations = set()
    max_iterations = 20  # safety limit

    for _ in range(max_iterations):
        # Re-query the table fresh every iteration since it re-renders after each save
        location_rows = page.locator("tr.MuiTableRow-root:has-text('CORP-Brand')")
        total_locations = location_rows.count()

        target_row = None
        target_name = None

        for i in range(total_locations):
            row = location_rows.nth(i)
            name = row.locator("td").nth(1).inner_text().strip()
            if name not in processed_locations:
                target_row = row
                target_name = name
                break

        if target_row is None:
            print("All locations processed.")
            break


        # Find Edit button using aria-label in the last column
        editTask = target_row.locator("td").last.locator("button[aria-label='Edit task']")
        editTask.wait_for(state="visible", timeout=30000)
        editTask.click()
        print("Edit Task clicked")
        page.wait_for_timeout(3000)

        criticalDates = page.get_by_role("button", name="Critical Dates")
        criticalDates.wait_for(state="visible", timeout=30000)
        criticalDates.click()
        print("Critical Dates opened")
        page.wait_for_timeout(3000)

        customerDesiredDueDate = page.locator(
            'div.MuiInputBase-root:has(input[name="Customer Desired Due Date"]) button'
        )
        customerDesiredDueDate.wait_for(state="visible", timeout=30000)
        customerDesiredDueDate.click()
        page.wait_for_timeout(3000)

        pick_date(page, date.today() + timedelta(days=6))
        print("Date selected")
        page.wait_for_timeout(3000)

        customerDesireSave = page.get_by_role("button", name="SAVE", exact=True).first
        customerDesireSave.wait_for(state="visible", timeout=30000)
        customerDesireSave.click()
        print("Customer desired date saved")
        page.wait_for_timeout(3000)

        close = page.get_by_role("button", name="close")
        close.wait_for(state="visible", timeout=30000)
        close.click()
        print("Task closed")
        page.wait_for_timeout(5000)

        processed_locations.add(target_name)
        print(f"Completed: {target_name}")

    print(f"\n{'='*50}")
    print("All locations processed")
    print("Completing task...")
    print(f"{'='*50}")

    complete.wait_for(state="visible", timeout=30000)
    complete.click()
    page.wait_for_timeout(3000)
    print("Task completed successfully")
    # ESTABLISH SITE ROLLOUT GROUPS________________________________________
    estabilishSiteRollout.wait_for(state="visible", timeout=30000)
    estabilishSiteRollout.click()
    page.wait_for_timeout(1000)
    add.wait_for(state="visible", timeout=30000)
    add.click() 
    page.wait_for_timeout(1000)
    siteName.fill(group_name)
    siteSave.click()
    page.wait_for_timeout(2000)
    checkboxes = page.locator('tbody input[type="checkbox"]').all()
    for idx, checkbox in enumerate(checkboxes, 1):
        checkbox.check()
        print(f"Checked checkbox {idx}")
        page.wait_for_timeout(3000)
    associate.click()
    page.wait_for_timeout(1000)
    page.wait_for_timeout(1000)
    associateclose.click()
    page.wait_for_timeout(1000)
    grpCheckBox.check()
    page.wait_for_timeout(1000)
    createSubProject.click()
    page.wait_for_timeout(1000)
    grpCheckBox.check()
    page.wait_for_timeout(1000)
    complete.click()

    context.close()
    browser.close()
with sync_playwright() as playwright:
    run(playwright)
    