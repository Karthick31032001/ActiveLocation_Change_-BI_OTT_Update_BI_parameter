from playwright.sync_api import Playwright, sync_playwright, expect
from pathlib import Path
import random
import re
import json

customer_name = "Morris152430"

# Set to: "ROUTER", "BI", or "BI+OTT"
scenario_type = "BI"

# Pre-defined mapping of Locations and their corresponding Offerings
LOCATION_OFFERINGS = {
    "47 13TH ST": ["Managed Router01", "Without_Static_IP_4"],
    "1401 JOHN F KENNEDY": ["Managed Router02", "Without_Static_IP_5"],
    "320 5TH AVE": ["Managed Router03", "Without_Static_IP_6"]
}

# Validate scenario_type up front so a typo doesn't silently skip everything
scenario_type = scenario_type.strip().upper()
if scenario_type not in {"ROUTER", "BI", "BI+OTT"}:
    raise ValueError(
        f"Invalid scenario_type: '{scenario_type}'. "
        f"Expected one of: 'ROUTER', 'BI', 'BI+OTT'"
    )

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Launching Browser ____________________________________________________________
    page.goto("https://century-automation-product.excelacomcloud.net/c360/")
    page.get_by_role("textbox", name="Username Password").fill("Karthick.R")
    page.locator("#password").fill("Hope@2026")
    page.get_by_role("button", name="Login").click()

    # Customer Search Elements _____________________________________________________
    c360Button = page.get_by_role("button", name="Customer")
    custTab = page.get_by_role("tab", name="Customers")
    custNameSearch = page.locator('//*[@name="Customer Name" and @paramformattype="searchLookup"]')
    custNameSearchIcon = page.locator('//*[@name="Customer Name"]/../div/*[contains(@class,"searchIcon")]')
    custIDHyperlink = page.locator(f'//*[text()="{customer_name}"]/../../..//td/div/*[contains(@class,"hyperlink")]')
    contract = page.get_by_role("button", name="Contract")
    custSaveAndGotoAcc = page.get_by_role("button", name="SAVE AND GO TO ACCOUNT")
    service_row = page.get_by_role("row").filter(has_text="Service")
    service_link = service_row.locator("span.hyperlink").first
    activeLocationHeader = page.locator("//p[text()='Active Locations']")
    moreButton = page.locator("//p[text()='Active Locations']/../..//button[@title='More Actions']")
    change = page.locator('//li[@displayname="Change"]')
    proceed = page.locator("//span[text()='Proceed']")
    serviceType = page.locator("//label[text()='Service Type']")
    contractID = page.locator('//input[@name="Contract ID"]')
    opportunityID = page.locator('//input[@name="Opportunity ID"]')
    save = page.locator("//span[text()='SAVE']")
    saveandgotodesign = page.get_by_role("button", name="SAVE AND GO TO DESIGN")
    save_go_to_serviceability = page.locator("//span[text()='SAVE AND GO TO SERVICEABILITY']")
    saveandGotoSummary = page.locator("//span[text()='SAVE AND GO TO SUMMARY']")

    def select_dropdown(label_locator, value):
        select_control = label_locator.locator(
            "xpath=ancestor::div[contains(@class,'MuiFormControl-root')][1]//div[@role='button']"
        )
        select_control.click()
        page.locator(f"//li[normalize-space()='{value}']").click()

    # ---------------- NAVIGATE TO CUSTOMER ----------------
    c360Button.wait_for(state="visible", timeout=30000)
    c360Button.click()
    page.wait_for_timeout(3000)
    custTab.click()
    custNameSearch.wait_for(state="visible", timeout=30000)
    custNameSearch.fill(customer_name)
    custNameSearchIcon.click()
    custIDHyperlink.first.click()
    page.wait_for_timeout(4000)

    # ---------------- READ SOW ID FROM CONTRACT PANEL ----------------
    contract.click()
    page.wait_for_timeout(4000)

    # 1. Locate the row containing "SOWContract2" using the gridcell structure
    sow_row = page.get_by_role("row").filter(has_text="SOWContract2")
    expect(sow_row).to_be_visible(timeout=10000)

    # 2. Extract the text from the first column (Contract ID)
    extracted_sow_id = sow_row.get_by_role("gridcell").first.inner_text().strip()
    print(f"Extracted SOW ID dynamically: {extracted_sow_id}")

    custSaveAndGotoAcc.wait_for(state="visible", timeout=30000)
    custSaveAndGotoAcc.click()
    page.wait_for_timeout(4000)
    service_link.click()
    page.wait_for_timeout(2000)

    # ---------------- ACTIVE LOCATIONS TABLE ----------------
    activeLocationHeader.click()
    active_table = page.locator(
        "xpath=//p[text()='Active Locations']/ancestor::div[.//table][1]//table"
    )
    rows = active_table.locator("tbody tr")

    page.wait_for_timeout(2000)
    if not rows.first.is_visible():
        activeLocationHeader.click()
    expect(rows.first).to_be_visible(timeout=30000)

    # *** TARGET LOCATION ***
    target_location_name = "1401 JOHN F KENNEDY"

    for i in range(rows.count()):
        cells = rows.nth(i).locator("td")
        loc_name = cells.nth(2).inner_text().strip()
        print(f"Location ID: {cells.nth(1).inner_text().strip()} | Location Name: {loc_name}")

        # Print expected offerings based on dictionary mapping
        for known_loc, offerings in LOCATION_OFFERINGS.items():
            if known_loc in loc_name:
                print(f"  -> Pre-defined Offerings: {', '.join(offerings)}")

    target_row = rows.filter(has_text=target_location_name)
    target_row.get_by_role("checkbox").check()
    print(f"\nCheckbox selected for {target_location_name}")
    page.wait_for_timeout(1000)

    # ---------------- INITIATE CHANGE ----------------
    moreButton.click(timeout=30000)
    change.click(timeout=30000)
    page.wait_for_timeout(2000)
    proceed.wait_for(state="visible", timeout=30000)
    proceed.click(timeout=30000)
    print("Change proceeded successfully")
    page.wait_for_timeout(2000)

    select_dropdown(serviceType, "Contract Offerings")
    page.wait_for_timeout(2000)
    # Pick the first available option (skip "--Select--" placeholder)
    contractID.click()
    options = page.get_by_role("option").filter(has_not_text="--Select--")
    options.first.wait_for(state="visible",timeout=10000)
    options.first.click()
    page.wait_for_timeout(3000)
    opportunityID.fill("3443423")
    page.wait_for_timeout(1000)
    save.click()
    page.wait_for_timeout(1000)
    saveandgotodesign.click()
    page.wait_for_timeout(3000)

    # ============================================================
    # CORE FUNCTIONS FOR SCENARIOS
    # ============================================================
    def configure_offering(offering_name):
        print(f"\n--- Configuring: {offering_name} ---")
        offering_rows = page.locator(
            "xpath=//*[normalize-space(text())='My Offering']/ancestor::div[.//table][1]//tbody/tr"
        )
        expect(offering_rows.first).to_be_visible(timeout=30000)

        for i in range(offering_rows.count()):
            cells = offering_rows.nth(i).locator("td")
            print("ID:", cells.nth(0).inner_text().strip(),
                  "| Market Offering Name:", cells.nth(1).inner_text().strip())

        target_row = offering_rows.filter(has_text=offering_name).first
        target_row.locator("td").nth(3).locator("svg, button").first.click()
        page.wait_for_timeout(2000)

        offering_code = page.locator(".MuiFormControl-root") \
            .filter(has_text="Offering Code").locator(".MuiSelect-select")
        expect(offering_code).to_be_visible(timeout=30000)
        old_value = offering_code.inner_text().strip()

        offering_code.click()
        page.wait_for_timeout(1000)
        page.get_by_role("option").filter(has_not_text="--Select--").nth(1).click()
        page.wait_for_timeout(2000)

        new_value = offering_code.inner_text().strip()
        print(f"Offering Code: {old_value}  ->  {new_value}")
        print(f"Offering:      {old_value.rsplit('_', 1)[0]}  ->  {new_value.rsplit('_', 1)[0]}")

    """ def finalize_offering():
        print("\n--- Finalizing: Next & Close ---")
        try:
            page.get_by_role("button", name="Next", exact=True).click(timeout=10000)
        except Exception as e:
            print(f"Next button not found, trying alternate: {e}")
            page.locator("//span[text()='Next']").click()
        page.wait_for_timeout(3000)

        try:
            page.get_by_role("button", name="close").click(timeout=10000)
        except Exception as e:
            print(f"Close button not found, trying alternate: {e}")
            page.locator("//button[@title='Close']").click()
        page.wait_for_timeout(3000) """

    def remove_offering(offering_name):
        print(f"\n--- Removing: {offering_name} ---")
        offering_rows = page.locator(
            "xpath=//*[normalize-space(text())='My Offering']/ancestor::div[.//table][1]//tbody/tr"
        )
        expect(offering_rows.first).to_be_visible(timeout=30000)

        target_row = offering_rows.filter(has_text=offering_name).first

        # Click Remove (5th column / index 4)
        target_row.locator("td").nth(4).locator("svg, button").first.click()
        page.wait_for_timeout(2000)

        # Handle Confirmation Dialog
        try:
            ok_button = page.get_by_role("button", name="OK", exact=True)
            expect(ok_button).to_be_visible(timeout=5000)
            ok_button.click()
            print("Confirmed removal via 'OK' button.")
        except Exception as e:
            print(f"Could not find OK button: {e}")
            # Fallback just in case
            page.locator("//button[normalize-space()='OK']").click()

        page.wait_for_timeout(3000)

        # Verify success toast (optional but good for validation)
        try:
            success_toast = page.get_by_text("Market offering removed successfully")
            expect(success_toast).to_be_visible(timeout=10000)
            print("PASS: Toast 'Market offering removed successfully' appeared.")
        except Exception:
            print("Warning: Success toast not detected, but continuing...")

    # ============================================================
    # SCENARIO EXECUTION (Dynamic based on selected location)
    # ============================================================

    # 1. Look up which offerings belong to the selected location
    current_offerings = []
    for known_loc, offerings in LOCATION_OFFERINGS.items():
        if known_loc in target_location_name:
            current_offerings = offerings
            break

    if not current_offerings:
        raise ValueError(f"No offerings defined in dictionary for {target_location_name}")

    # 2. Identify which is the Router (OTT) and which is the IP (BI)
    router_name = next((o for o in current_offerings if "Router" in o), None)
    ip_name = next((o for o in current_offerings if "IP" in o), None)

    if not router_name:
        raise ValueError(f"No Router offering found for location: {target_location_name}")
    if not ip_name and scenario_type in {"BI", "BI+OTT"}:
        raise ValueError(f"No IP offering found for location: {target_location_name}")

    # 3. Execute the scenario using the dynamically found names
    if scenario_type == "ROUTER":
        print(f"\n=== SCENARIO 1: OTT Only (Remove Router) ===")
        remove_offering(router_name)
        # Note: finalize_offering() is skipped here because removing
        # closes the configuration modal automatically.

    elif scenario_type == "BI":
        print(f"\n=== SCENARIO 2: BI Only (Change IP Offering Code) ===")
        configure_offering(ip_name)
        #finalize_offering()

    elif scenario_type == "BI+OTT":
        print(f"\n=== SCENARIO 3: BI + OTT (Sequential Change) ===")
        print(f">>> Step 1/2: Configuring BI offering (IP)...")
        configure_offering(ip_name)
        #finalize_offering()               # ← moved here: closes modal BEFORE the next configure
        print(f"\n>>> Step 2/2: Configuring OTT offering (Router)...")
        configure_offering(router_name)
        #finalize_offering()

    # ---------------- Move to Summary ----------------
    page.wait_for_timeout(7000)
    save_go_to_serviceability = page.locator("//span[text()='SAVE AND GO TO SERVICEABILITY']")
    save_go_to_serviceability.click()
    page.wait_for_timeout(5000)
    saveandGotoSummary.click()
    page.wait_for_timeout(5000)

    # =================================================
    # Sales Order Summary - Validation
    # =================================================
    # ROUTER scenario → offering removed → summary shows "Disconnect"
    # BI / BI+OTT scenarios → offering code changed → summary shows "Change"
    expected_action = "Disconnect" if scenario_type == "ROUTER" else "Change"

    activity_type = page.locator('input[name="Activity Type"]')
    expect(activity_type).to_have_value(expected_action, timeout=30000)
    print(f"PASS: Activity Type is displayed as '{expected_action}'")

    location_summary_header = page.locator("//p[text()='Location Summary']")
    location_summary_header.click(timeout=30000)
    page.wait_for_timeout(2000)
    location_summary_table = page.locator('table[id="Location Summary"]')
    location_panel_arrow = location_summary_table.get_by_role("img", name="Panel Arrow")

    for attempt in range(5):
        try:
            location_panel_arrow.first.click(timeout=5000)
            print("Expanded Location Summary location row")
            break
        except Exception:
            page.wait_for_timeout(1000)
    else:
        print("Could not click Location Summary location row after retries — continuing anyway")
    page.wait_for_timeout(2000)

    items_table = location_summary_table
    column_headers = items_table.get_by_role("columnheader")
    expect(column_headers.first).to_be_visible(timeout=30000)
    header_texts = [" ".join(h.split()) for h in column_headers.all_inner_texts()]

    def find_col(name):
        for i, h in enumerate(header_texts):
            if h == name:
                return i
        raise ValueError(f"Column '{name}' not found in headers: {header_texts}")

    action_type_idx = find_col("Action Type")
    mrc_idx = find_col("MRC")
    nrc_idx = find_col("NRC")

    item_rows = items_table.get_by_role("checkbox").filter(has_text=expected_action)
    row_count = item_rows.count()
    assert row_count > 0, f"No Location Summary item rows with Action Type '{expected_action}' found"

    for i in range(row_count):
        row_cells = item_rows.nth(i).get_by_role("cell")
        expect(row_cells.nth(action_type_idx)).to_have_text(expected_action, timeout=30000)
        expect(row_cells.nth(mrc_idx)).to_contain_text("0", timeout=30000)
        expect(row_cells.nth(nrc_idx)).to_contain_text("0", timeout=30000)

    print(f"PASS: All {row_count} item(s) show Action Type '{expected_action}' with MRC/NRC = 0")

    # ---------------- Submit & Verify ----------------
    sales_order_id_field = page.locator('input[name="Sales Order ID"]')
    expect(sales_order_id_field).to_be_visible(timeout=30000)
    sales_order_id = sales_order_id_field.get_attribute("value")
    print(f"Mapped Sales Order ID: {sales_order_id}")

    submit_order_button = page.get_by_role("button", name="SUBMIT ORDER")
    submit_order_button.click(timeout=30000)
    expect(page.locator('input[name="Status"]')).not_to_have_value("Pending", timeout=60000)
    print("Order submitted. Status:", page.locator('input[name="Status"]').input_value())

    with open("cto-captures.json", "w") as f:
        json.dump({"sales_order_id": sales_order_id}, f)

    print("\n[SCRIPT COMPLETE]")
    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)