from playwright.sync_api import Playwright, sync_playwright, expect
import calendar
import json
import re
import os
from datetime import date, timedelta

OUTPUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cto-captures.json")
customer_name = "{{store.BI_OTT}}"

_MONTHS = {
    name: i
    for i, name in enumerate(calendar.month_name)
    if name
}


# ==========================================================
# SMALL HELPERS
# ==========================================================
def _is_browser_dead(page, context):
    try:
        if page.is_closed():
            return True
        if not context.pages:
            return True
        return False
    except Exception:
        return True


def cell_text(cell):
    """Return visible text, or title/aria-label if truncated/empty."""
    try:
        txt = cell.inner_text().strip()
        if txt:
            return txt
    except Exception:
        pass
    for sel in ("[title]", "[aria-label]"):
        try:
            el = cell.locator(sel).first
            if el.count() > 0:
                for attr in ("title", "aria-label"):
                    v = el.get_attribute(attr)
                    if v and v.strip():
                        return v.strip()
        except Exception:
            pass
    try:
        v = cell.get_attribute("title")
        if v:
            return v.strip()
    except Exception:
        pass
    return ""


def _read_activity_type(page):
    """Read Activity Type from the Product Order section."""
    candidates = [
        "//label[normalize-space()='Activity Type']/following::input[1]",
        "//label[contains(normalize-space(),'Activity Type')]/following::input[1]",
        "//*[contains(normalize-space(text()),'Activity Type')]/following::input[1]",
        "//label[normalize-space()='Order Type']/following::input[1]",
        "//label[contains(normalize-space(),'Order Type')]/following::input[1]",
    ]
    for xp in candidates:
        try:
            loc = page.locator(xp).first
            if loc.count() > 0:
                val = loc.input_value().strip()
                if val:
                    return val
        except Exception:
            continue
    return ""


def col_index(headers, *candidates):
    """Return index of first header matching any candidate (case-insensitive contains)."""
    for c in candidates:
        for i, h in enumerate(headers):
            if c.lower() in h.lower():
                return i
    return None


def pick_date(page, target):
    """Move the open calendar to the required month/year and click the required day."""
    calendar_header = page.locator(".MuiPickersCalendarHeader-transitionContainer")
    calendar_header.wait_for(state="visible", timeout=30000)
    for _ in range(24):
        page.wait_for_timeout(500)
        shown = calendar_header.inner_text().strip()
        parts = shown.split()
        month_name = parts[0]
        year = parts[1]
        shown_year = int(year)
        shown_month = _MONTHS[month_name]
        if (shown_year, shown_month) == (target.year, target.month):
            break
        if (shown_year, shown_month) < (target.year, target.month):
            page.locator(".MuiPickersCalendarHeader-switchHeader button").last.click()
        else:
            page.locator(".MuiPickersCalendarHeader-switchHeader button").first.click()
    page.locator(
        f"//button[contains(@class,'MuiPickersDay-day') "
        f"and not(contains(@class,'MuiPickersDay-hidden')) "
        f"and normalize-space()='{target.day}']"
    ).click()


def print_side_by_side(expected_list, actual_list, title):
    """Prints a side-by-side comparison table for all milestones."""
    print(f"\n      === {title} ===")
    print(f"      {'EXPECTED':<52} | {'EXTRACTED':<52}")
    print(f"      {'-'*52}-+-{'-'*52}")

    max_len = max(len(expected_list), len(actual_list))
    for i in range(max_len):
        exp = expected_list[i] if i < len(expected_list) else "<MISSING>"
        act = actual_list[i] if i < len(actual_list) else "<MISSING>"

        e, a = exp.lower(), act.lower()
        match = (e in a or a in e)
        marker = " " if match else "X"

        print(f"      {i+1:>2}. {exp[:48]:<48} | {i+1:>2}. {act[:48]:<48} {marker}")
    print(f"      {'-'*52}-+-{'-'*52}")


# ==========================================================
# EDIT TASK FUNCTION
# ==========================================================
def edit_task(page, task_name):
    print(f"Starting edit: {task_name}")
    task_row = page.get_by_role("row").filter(has_text=task_name).first
    expect(task_row).to_be_visible(timeout=30000)
    task_row.get_by_role("button").first.click(timeout=30000)
    page.wait_for_timeout(2000)

    today = date.today()
    today_day = str(today.day)

    page.get_by_role("button", name="change date").first.click(timeout=30000)
    page.get_by_role("button", name=today_day, exact=True).click(timeout=30000)

    page.get_by_role("button", name="change date").nth(1).click(timeout=30000)
    page.get_by_role("button", name=today_day, exact=True).click(timeout=30000)


# ==========================================================
# MAIN FLOW
# ==========================================================
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(60000)

    username = page.get_by_role("textbox", name="Username Password")
    password = page.locator("#password")
    login_button = page.get_by_role("button", name="Login")
    projects_tab = page.get_by_role("tab", name="Projects")
    my_projects_tab = page.get_by_role("tab", name="My Projects")
    customer_input = page.locator('input[name="Customer Name"]')
    search_icon = customer_input.locator(
        "xpath=following-sibling::div//*[name()='svg' and contains(@class,'searchIcon')]"
    )
    project_management_button = page.get_by_role("button", name="Project Management")
    in_progress_sites_tab = page.get_by_role("tab", name="InProgress Sites")
    refresh_button = page.get_by_role("button", name="Refresh Refresh")

    # 1. Login
    page.goto("{{env.pm}}")
    username.wait_for(state="visible", timeout=30000)
    username.fill("Karthick.R")
    password.fill("Hope@2026")
    login_button.click()

    project_management_button.wait_for(state="visible", timeout=30000)
    project_management_button.click()
    page.wait_for_timeout(3000)
    projects_tab.wait_for(state="visible", timeout=30000)
    projects_tab.click()
    page.wait_for_timeout(3000)
    my_projects_tab.wait_for(state="visible", timeout=30000)
    my_projects_tab.click()
    page.get_by_role("tab", name="All Projects").wait_for(state="visible", timeout=30000)
    page.get_by_role("tab", name="All Projects").click()

    # 2. Customer Selection
    customer_input.wait_for(state="visible", timeout=30000)
    customer_input.click()
    customer_input.fill(customer_name)
    search_icon.click()

    row = page.locator("tr.MuiTableRow-root", has_text=customer_name)
    row.locator("span.hyperlink").first.click()
    page.wait_for_timeout(500)

    # 3. In-Progress Sites Extraction
    in_progress_sites_tab.wait_for(state="visible", timeout=30000)
    in_progress_sites_tab.click()
    page.wait_for_timeout(5000)

    refresh_span = page.locator("//span[text()='Refresh']")
    refresh_span.wait_for(state="visible", timeout=30000)
    refresh_span.click()
    page.wait_for_timeout(2000)
    refresh_span.click()
    page.wait_for_timeout(2000)
    refresh_button.wait_for(state="visible", timeout=30000)

    product_order_cells = page.locator('td[data-colindex="0"]:visible').filter(
        has_not_text="NO DATA AVAILABLE"
    )
    for _attempt in range(15):
        if product_order_cells.count() > 0:
            break
        page.wait_for_timeout(1000)
    else:
        raise AssertionError("No Product Order ID appeared under InProgress Sites")

    location_name_cells = page.locator('td[data-colindex="4"]:visible')
    row_count = product_order_cells.count()
    rows_meta = []
    for i in range(row_count):
        pid = product_order_cells.nth(i).inner_text().strip()
        loc_name = location_name_cells.nth(i).inner_text().strip()
        rows_meta.append((pid, loc_name))
        print(f"Product Order ID: {pid} | Location Name (listing) = {loc_name}")

    # ==========================================================
    # EXTRACT AND SAVE PRODUCT ORDER IDs
    # ==========================================================
    product_order_ids = []
    for pid, _ in rows_meta:
        if pid.isdigit() and pid not in product_order_ids:
            product_order_ids.append(pid)

    print("\n===== Product Order IDs =====")
    for pid in product_order_ids:
        print(pid)
    print("=============================\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"product_order_ids": product_order_ids}, f, indent=2)
    print(f"Product Order IDs saved → {OUTPUT_JSON}\n")

    # ==========================================================
    # HELPERS USED PER PO
    # ==========================================================
    def is_on_listing_page():
        try:
            return page.locator('td[data-colindex="0"]:visible').count() > 0
        except Exception:
            return False

    def wait_for_detail_page(timeout_ms=15000):
        try:
            page.locator(
                "//label[contains(normalize-space(),'Activity Type') or "
                "contains(normalize-space(),'Order Type')]/following::input[1]"
            ).first.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def return_to_product_order():
        try:
            product_order_span = page.locator(
                "xpath=//nav[@aria-label='breadcrumb']//span[normalize-space(text())='Product Order']"
            ).first

            if product_order_span.count() > 0:
                product_order_span.click(force=True)
                print("      🔙 Navigated back to Product Order page.")
            else:
                page.locator("nav[aria-label='breadcrumb'] li").filter(has_text="Product Order").first.click(force=True)
                print("      🔙 Navigated back to Product Order page (fallback).")

            page.wait_for_timeout(4000)

        except Exception as e:
            print(f"      ⚠️ Error navigating back to Product Order: {e}")
            try:
                page.go_back()
                page.wait_for_timeout(3000)
            except:
                pass

    # ==========================================================
    # 4. PRODUCT ORDER PROCESSING LOOP
    # ==========================================================
    records_by_ext = {}

    for pid, loc_name_from_listing in rows_meta:
        if _is_browser_dead(page, context):
            print("❌ Browser/page was closed — stopping pipeline.")
            break

        print(f"\n--- Processing Product Order ID: {pid} ---")

        try:
            # ---------- OPEN PO DETAIL ----------
            navigated = False
            for attempt in (1, 2):
                try:
                    page.locator('td[data-colindex="0"]:visible').first.wait_for(
                        state="visible", timeout=15000
                    )
                    page.wait_for_timeout(800)
                    po_row = (
                        page.locator("tr.MuiTableRow-root")
                        .filter(
                            has=page.locator(
                                'td[data-colindex="0"]',
                                has_text=re.compile(rf"^\s*{re.escape(pid)}\s*$"),
                            )
                        )
                        .first
                    )
                    po_link = po_row.locator("span.hyperlink").first
                    po_link.scroll_into_view_if_needed()
                    po_link.wait_for(state="visible", timeout=15000)
                    po_link.click()
                    page.wait_for_timeout(2500)
                    if wait_for_detail_page(timeout_ms=8000):
                        navigated = True
                        break
                    else:
                        print(f"   ⚠️  Click on PO {pid} didn't open detail (attempt {attempt})")
                        if is_on_listing_page():
                            continue
                except Exception as e:
                    print(f"   ❌ Click error on PO {pid} (attempt {attempt}): {e}")

            if not navigated:
                print(f"   ⏭️  Skipping PO {pid} — could not open detail page.")
                if not is_on_listing_page():
                    return_to_product_order()
                continue

            # ==========================================================
            # OPTIONAL: OTT ORDER ENRICHMENT (Skip if not present)
            # ==========================================================
            print("\n[OPTIONAL] Checking for OTT Order Enrichment task...")
            try:
                ott_Order_Enrichment = page.get_by_text("OTT Order Enrichment", exact=True)

                ott_Order_Enrichment.wait_for(state="visible", timeout=5000)
                print("   ✅ OTT Order Enrichment found. Executing...")

                ott_Order_Enrichment.click()
                page.wait_for_timeout(3000)

                # --- Match Solution Group ---
                checkBox = page.locator("tr.MuiTableRow-root", has_text="CORP-Brand#01").first.locator('input[id^="MUIDataTableSelectCell-"]')
                checkBox.check()
                page.wait_for_timeout(2000)

                moreButton = page.locator('//button[@aria-label="more"]')
                moreButton.wait_for(state="visible", timeout=30000)
                moreButton.click()
                page.wait_for_timeout(2000)

                matchsolutionGroup = page.locator("//li[text()='MATCH SOLUTION GROUP']")
                matchsolutionGroup.wait_for(state="visible", timeout=30000)
                matchsolutionGroup.click()
                page.wait_for_timeout(3000)

                refresh_button.click()
                page.wait_for_timeout(5000)

                # Retry (UI issue)
                checkBox = page.locator("tr.MuiTableRow-root", has_text="CORP-Brand#01").first.locator('input[id^="MUIDataTableSelectCell-"]')
                checkBox.check()
                page.wait_for_timeout(2000)

                moreButton = page.locator('//button[@aria-label="more"]')
                moreButton.wait_for(state="visible", timeout=30000)
                moreButton.click()
                page.wait_for_timeout(2000)

                matchsolutionGroup = page.locator("//li[text()='MATCH SOLUTION GROUP']")
                matchsolutionGroup.wait_for(state="visible", timeout=30000)
                matchsolutionGroup.click()
                page.wait_for_timeout(3000)

                refresh_button.click()
                page.wait_for_timeout(5000)
                refresh_button.click()
                page.wait_for_timeout(2000)

                # --- Edit Critical Dates ---
                editIcon = page.locator("tbody tr").filter(has_text="CORP-Brand#01").get_by_title("Edit", exact=True)
                editIcon.click()
                page.wait_for_timeout(6000)

                truckrolldate = page.locator('//input[@name="Truck Roll Requested Date"]')
                equipneededdate = page.locator('//input[@name="Equipment Need By Date"]')

                def select_dropdown(input_locator, value):
                    clickable = input_locator.locator("xpath=preceding-sibling::div[@role='button']")
                    clickable.click()
                    page.locator(f"//li[normalize-space()='{value}']").click()

                today = date.today()
                start_date = today + timedelta(days=4)
                end_date = today + timedelta(days=6)

                truckrolldate.wait_for(state="visible", timeout=30000)
                truckrolldate.first.click()
                pick_date(page, start_date)
                page.wait_for_timeout(2000)

                equipneededdate.wait_for(state="visible", timeout=30000)
                equipneededdate.click()
                pick_date(page, end_date)

                truckSubmittedby = page.locator('//input[@name="Truck Roll Submitted By"]')
                truckSubmittedby.fill("Customer")

                truckrollType = page.locator('//input[@name="Truck Roll Type"]')
                select_dropdown(truckrollType, "Equipment Warranty")

                schedulingParameter = page.locator('//input[@name="Scheduling Parameter"]')
                select_dropdown(schedulingParameter, "Week Of")

                page.wait_for_timeout(3000)

                save = page.locator('//button[@entityname="Critical Dates"][@name="Save"]')
                save.click()
                page.wait_for_timeout(3000)

                close = page.locator('//div[@name="Critical Dates"]/../../../..//button[@aria-label="close"]')
                close.wait_for(state="visible", timeout=30000)
                close.click()
                page.wait_for_timeout(4000)

                checkBox = page.locator("tr.MuiTableRow-root", has_text="CORP-Brand#01").first.get_by_role("checkbox")
                checkBox.check()

                complete = page.locator('//button[@name="COMPLETE"]')
                complete.click()
                page.wait_for_timeout(3000)

                print("   ✅ OTT Order Enrichment flow completed.")

            except Exception as e:
                print(f"   ⏭️  OTT Order Enrichment not present or skipped. Proceeding with the rest of the flow.")
                print(f"      Reason: {type(e).__name__}: {str(e)[:100]}")

            # ==========================================================
            # BI+OTT MILESTONE VALIDATION
            # ==========================================================
            print("\n   [==================================================]")
            print("   [  BI+OTT Product Order Milestones Validation      ]")
            print("   [==================================================]")

            try:
                mo_tbl = None
                headers = []
                for _ in range(10):
                    for t in page.locator("table").all():
                        try:
                            heads = [h.strip() for h in t.locator("th").all_inner_texts()]
                            if any(re.search(r"Market Offering I[dD]", h, re.IGNORECASE) for h in heads):
                                mo_tbl = t
                                headers = [
                                    h.inner_text().strip().replace("\n", " ")
                                    for h in t.locator("thead th").all()
                                ]
                                break
                        except Exception:
                            continue
                    if mo_tbl:
                        break
                    page.wait_for_timeout(1000)

                service_provider = None
                found_router = False
                found_without_static = False

                if mo_tbl is not None and mo_tbl.count() > 0:
                    mo_name_idx = col_index(headers, "Market Offering Name") or 1
                    view_idx = col_index(headers, "View")
                    if view_idx is None:
                        view_idx = len(headers) - 2

                    total_rows = mo_tbl.locator("tr:has(td)").count()

                    for i in range(total_rows):
                        current_row = mo_tbl.locator("tr:has(td)").nth(i)
                        mo_name = cell_text(current_row.locator("td").nth(mo_name_idx))
                        mo_name_lower = mo_name.lower()

                        folder_cell = current_row.locator("td").nth(view_idx)
                        folder_icon = folder_cell.locator("svg, img, [role='button'], button, a").first

                        # CASE A: MANAGED ROUTER
                        if "managed router" in mo_name_lower:
                            found_router = True
                            print(f"      Found '{mo_name}'. Checking Configuration Milestones...")
                            if folder_icon.count() > 0:
                                folder_icon.click()
                                page.wait_for_timeout(4000)

                                raw_labels = page.locator('//span[@class="stepperLabel"]').all_text_contents()
                                actual_router_milestones = []
                                for raw in raw_labels:
                                    clean = re.sub(r"\d{2}-\d{2}-\d{4}", "", raw).strip()
                                    clean = clean.replace("...", "").strip()
                                    clean = " ".join(clean.split())
                                    if clean:
                                        actual_router_milestones.append(clean)

                                managed_router_expected = [
                                    "Order Received", "Order Rejected after Acceptance", "Order Amended In-flight",
                                    "Intake Order Review", "Supply Chain Order Initiated", "Zeus Provisioning Initiated",
                                    "Field Services Planning Initiated", "WO Created", "TTUA Activation Initiated",
                                    "WO Rescheduled", "WO Resume", "WO Cancelled", "WO Assigned", "WO Re-assigned",
                                    "WO Work In-Progress", "WO Not Done", "WO Ready for Review", "WO Closed",
                                    "WO Suspended", "Supply Chain Order Created", "Supply Chain Order Cancelled",
                                    "Fulfillment Order Created", "Fulfillment Order Cancelled", "Shipment Created",
                                    "Equipment(s) Delivered", "Zeus Provisioning Completed", "TTUA Activation Completed",
                                    "Service Assurance Configuration Complete", "Zabbix Provisioning Complete",
                                    "Client Sign-off Received", "PONR", "Trigger Billing", "Additional Charges Completed",
                                    "Reconciliation Request Submitted And Pending Approval",
                                    "PO Approved For Invoicing", "Ready For Payment Submission", "Payment Released"
                                ]

                                print_side_by_side(managed_router_expected, actual_router_milestones, "Router Config (37 Steps)")

                                try:
                                    if len(actual_router_milestones) != len(managed_router_expected):
                                        raise AssertionError(
                                            f"Router Count Mismatch! Expected {len(managed_router_expected)}, found {len(actual_router_milestones)}"
                                        )
                                    for index, (actual, expected) in enumerate(zip(actual_router_milestones, managed_router_expected), start=1):
                                        e, a = expected.lower(), actual.lower()
                                        if not (e in a or a in e):
                                            raise AssertionError(
                                                f"Router Mismatch at Position {index}: Expected '{expected}', found '{actual}'"
                                            )
                                    print("      ✅ Managed Router Config Milestones Validation Passed.")
                                except AssertionError as e:
                                    print(f"      ❌ Validation Failed: {e}")

                                return_to_product_order()

                                # Metro Line View
                                print(f"\n      [Validating Metro Line View for '{mo_name}']")
                                last_cell = current_row.locator("td").last
                                milestone_icon = last_cell.locator("svg, img, [role='button'], button, a").first

                                if milestone_icon.count() > 0:
                                    milestone_icon.click()
                                    page.wait_for_timeout(4000)

                                    metro_nodes = page.locator("//div[contains(@class, 'react-flow__node')]//span[@class='label-header']")
                                    actual_metro_list = []
                                    for k in range(metro_nodes.count()):
                                        raw_text = metro_nodes.nth(k).inner_text().strip()
                                        clean = raw_text.replace("...", "").strip()
                                        if clean and clean not in actual_metro_list:
                                            actual_metro_list.append(clean)

                                    print_side_by_side(managed_router_expected, actual_metro_list, "Router Metro Line (37 Steps)")

                                    try:
                                        if len(actual_metro_list) != len(managed_router_expected):
                                            raise AssertionError(
                                                f"Metro Line Count Mismatch! Expected {len(managed_router_expected)}, found {len(actual_metro_list)}"
                                            )
                                        for index, (actual, expected) in enumerate(zip(actual_metro_list, managed_router_expected), start=1):
                                            e, a = expected.lower(), actual.lower()
                                            if not (e in a or a in e):
                                                raise AssertionError(
                                                    f"Metro Line Sequence Mismatch at Position {index}: Expected '{expected}', found '{actual}'"
                                                )
                                        print("      ✅ Metro Line Milestones Validation Passed.")
                                    except AssertionError as e:
                                        print(f"      ❌ Validation Failed: {e}")

                                    close_btn = page.locator("div[role='dialog']:visible button[aria-label='close'], div[role='dialog']:visible button[aria-label='Close']").first
                                    if close_btn.count() > 0:
                                        close_btn.click()
                                    else:
                                        page.keyboard.press("Escape")
                                    page.wait_for_timeout(2000)
                                else:
                                    print("      ⚠️ Milestone folder icon not found in the last column.")

                        # CASE B: WITHOUT STATIC IP
                        elif "without_static_ip" in mo_name_lower:
                            found_without_static = True
                            print(f"      Found '{mo_name}'. Checking Service Provider...")
                            if folder_icon.count() > 0:
                                folder_icon.click()
                                page.wait_for_timeout(4000)

                                try:
                                    provider_input = page.locator(
                                        "//label[contains(text(), 'Service Provider')]/following::input[1] "
                                        "| //label[contains(text(), 'Service Provider')]/following::div[contains(@class, 'MuiInputBase-root')][1]//input"
                                    ).first
                                    if provider_input.count() > 0:
                                        service_provider = provider_input.input_value().strip()
                                    else:
                                        provider_div = page.locator("//label[contains(text(), 'Service Provider')]/..").first
                                        service_provider = provider_div.inner_text().replace("Service Provider", "").replace("*", "").strip()
                                    print(f"      Service Provider detected: '{service_provider}'")
                                except Exception as e:
                                    print(f"      ⚠️ Could not read Service Provider: {e}")

                                raw_labels = page.locator('//span[@class="stepperLabel"]').all_text_contents()
                                actual_config_list = []
                                for raw in raw_labels:
                                    clean = re.sub(r"\d{2}-\d{2}-\d{4}", "", raw).strip()
                                    clean = clean.replace("...", "").strip()
                                    clean = " ".join(clean.split())
                                    if clean:
                                        actual_config_list.append(clean)

                                productorder_configuration_comcast_expected = [
                                    "Designed", "Scheduled", "PONR", "Activated",
                                    "Trigger Billing", "Service Assurance Configuration Completed connectity service"
                                ]
                                productorder_configuration_standard_expected = [
                                    "Cost Approval Pending", "Cost Approval Completed", "Offnet Scheduled",
                                    "PONR", "Activated", "Trigger Billing",
                                    "Service Assurance Configuration Completed connectity service"
                                ]

                                if service_provider and "comcast" in service_provider.lower():
                                    expected_config_list = productorder_configuration_comcast_expected
                                    print(f"      Using Comcast list ({len(expected_config_list)} steps).")
                                else:
                                    expected_config_list = productorder_configuration_standard_expected
                                    print(f"      Using Standard list ({len(expected_config_list)} steps).")

                                print_side_by_side(expected_config_list, actual_config_list, f"BI Config ({len(expected_config_list)} Steps)")

                                try:
                                    if len(actual_config_list) != len(expected_config_list):
                                        raise AssertionError(
                                            f"Config Count Mismatch! Expected {len(expected_config_list)}, found {len(actual_config_list)}"
                                        )
                                    for index, (actual, expected) in enumerate(zip(actual_config_list, expected_config_list), start=1):
                                        e, a = expected.lower(), actual.lower()
                                        if not (e in a or a in e):
                                            raise AssertionError(
                                                f"Config Mismatch at Position {index}: Expected '{expected}', found '{actual}'"
                                            )
                                    print("      ✅ Config Milestones Validation Passed.")
                                except AssertionError as e:
                                    print(f"      ❌ Validation Failed: {e}")

                                return_to_product_order()

                                # Metro Line View
                                print(f"\n      [Validating Metro Line View for '{mo_name}']")
                                last_cell = current_row.locator("td").last
                                milestone_icon = last_cell.locator("svg, img, [role='button'], button, a").first

                                if milestone_icon.count() > 0:
                                    milestone_icon.click()
                                    page.wait_for_timeout(4000)

                                    metro_nodes = page.locator("//div[contains(@class, 'react-flow__node')]//span[@class='label-header']")
                                    actual_metro_list = []
                                    for k in range(metro_nodes.count()):
                                        raw_text = metro_nodes.nth(k).inner_text().strip()
                                        clean = raw_text.replace("...", "").strip()
                                        if clean and clean not in actual_metro_list:
                                            actual_metro_list.append(clean)

                                    print_side_by_side(expected_config_list, actual_metro_list, f"BI Metro Line ({len(expected_config_list)} Steps)")

                                    try:
                                        if len(actual_metro_list) != len(expected_config_list):
                                            raise AssertionError(
                                                f"Metro Line Count Mismatch! Expected {len(expected_config_list)}, found {len(actual_metro_list)}"
                                            )
                                        for index, (actual, expected) in enumerate(zip(actual_metro_list, expected_config_list), start=1):
                                            e, a = expected.lower(), actual.lower()
                                            if not (e in a or a in e):
                                                raise AssertionError(
                                                    f"Metro Line Sequence Mismatch at Position {index}: Expected '{expected}', found '{actual}'"
                                                )

                                        print("      ✅ Metro Line Milestones Validation Passed.")
                                    except AssertionError as e:
                                        print(f"      ❌ Validation Failed: {e}")

                                    close_btn = page.locator("div[role='dialog']:visible button[aria-label='close'], div[role='dialog']:visible button[aria-label='Close']").first
                                    if close_btn.count() > 0:
                                        close_btn.click()
                                    else:
                                        page.keyboard.press("Escape")
                                    page.wait_for_timeout(2000)
                                else:
                                    print("      ⚠️ Milestone folder icon not found in the last column.")

                # ==========================================================
                # DETECT ORDER MODE
                # ==========================================================
                if found_router and found_without_static:
                    order_mode = "BI+OTT"
                    print(f"\n      ℹ️ Detected Order Mode: {order_mode}")
                elif found_router and not found_without_static:
                    order_mode = "OTT-ONLY"
                    print(f"\n      ℹ️ Detected Order Mode: {order_mode}")
                elif not found_router and found_without_static:
                    order_mode = "BI-ONLY"
                    print(f"\n      ℹ️ Detected Order Mode: {order_mode}")
                else:
                    print("\n      ⚠️ Unknown Order Type. Skipping PO.")
                    continue

                # --- VALIDATE PO MILESTONES (PO DETAIL PAGE) ---
                print("\n      [Validating Product Order Top Stepper Milestones]")
                raw_labels_po = page.locator('//span[@class="stepperLabel"]').all_text_contents()
                actual_list = []
                for raw in raw_labels_po:
                    clean = re.sub(r"\d{2}-\d{2}-\d{4}", "", raw).strip()
                    clean = clean.replace("...", "").strip()
                    clean = " ".join(clean.split())
                    if clean:
                        actual_list.append(clean)

                # DYNAMIC TOP STEPPER LISTS
                if order_mode == "BI+OTT":
                    if service_provider and "comcast" in service_provider.lower():
                        expected_list = [
                            "Designed", "Scheduled", "OTT-Order Enrichment Task", "Connectivity PONR",
                            "Activated", "Billing Started", "Service Assurance Configuration Completed connectity service",
                            "Order Acceptance", "Equipment Ordering", "Scheduling", "Tracking",
                            "OTT PONR", "OTT Billing", "Closeout"
                        ]
                        print(f"      Using Comcast BI+OTT milestone list ({len(expected_list)} steps).")
                    else:
                        expected_list = [
                            "Cost Approval Pending", "Cost Approval Completed", "Offnet Scheduled",
                            "OTT-Order Enrichment Task", "Connectivity PONR", "Activated", "Billing Started",
                            "Service Assurance Configuration Completed connectity service", "Order Acceptance",
                            "Equipment Ordering", "Scheduling", "Tracking", "OTT PONR", "OTT Billing", "Closeout"
                        ]
                        print(f"      Using Standard BI+OTT milestone list ({len(expected_list)} steps).")

                elif order_mode == "BI-ONLY":
                    if service_provider and "comcast" in service_provider.lower():
                        expected_list = [
                            "Designed", "Scheduled", "Connectivity PONR", "Activated",
                            "Billing Started", "Service Assurance Configuration Completed connectity service"
                        ]
                        print(f"      Using Comcast BI-ONLY milestone list ({len(expected_list)} steps).")
                    else:
                        expected_list = [
                            ""
                        ]
                        print(f"      Using Standard BI-ONLY milestone list ({len(expected_list)} steps).")

                elif order_mode == "OTT-ONLY":
                    expected_list = [
                        "Order Acceptance", "Equipment Ordering", "Scheduling", "Tracking", "OTT PONR", "OTT Billing", "Closeout"
                    ]
                    print(f"      Using OTT-ONLY milestone list ({len(expected_list)} steps).")

                print_side_by_side(expected_list, actual_list, f"{order_mode} Top Stepper ({len(expected_list)} Steps)")

                # ISOLATED VALIDATION
                try:
                    if len(actual_list) != len(expected_list):
                        raise AssertionError(
                            f"Count Mismatch! Expected {len(expected_list)}, found {len(actual_list)}"
                        )
                    for index, (actual, expected) in enumerate(zip(actual_list, expected_list), start=1):
                        e, a = expected.lower(), actual.lower()
                        if not (e in a or a in e):
                            raise AssertionError(
                                f"Mismatch at Position {index}: Expected '{expected}', found '{actual}'"
                            )
                    print(f"   ✅ {order_mode} Top Stepper Validation Passed")
                except AssertionError as e:
                    print(f"   ❌ Validation Failed: {e}")

            except Exception as e:
                print(f"   ⚠️ Error during BI+OTT milestone validation: {e}")

            # ---------- CAPTURE FINAL DATA ----------
            mo_tbl = None
            headers = []
            for t in page.locator("table").all():
                try:
                    heads = [h.strip() for h in t.locator("th").all_inner_texts()]
                    if any(re.search(r"Market Offering I[dD]", h, re.IGNORECASE) for h in heads):
                        mo_tbl = t
                        headers = [
                            h.inner_text().strip().replace("\n", " ")
                            for h in t.locator("thead th").all()
                        ]
                        break
                except Exception:
                    continue

            activity_type = ""
            try:
                at_locator = page.locator("//label[normalize-space()='Activity Type']/following::input[1]").first
                if at_locator.count() == 0:
                    at_locator = page.locator("//label[contains(normalize-space(),'Activity Type')]/following::input[1]").first
                activity_type = at_locator.input_value().strip()
                print(f"   Activity Type = {activity_type!r}")
            except Exception as e:
                print(f"   ⚠️  Could not read Activity Type for PO {pid}: {e}")

            location_name = ""
            try:
                if mo_tbl is not None and mo_tbl.count() > 0 and headers:
                    loc_idx = next((i for i, h in enumerate(headers) if re.search(r"^Location$", h, re.IGNORECASE)), None)
                    rows_in_mo = mo_tbl.locator("tr:has(td)").all()
                    if rows_in_mo and loc_idx is not None:
                        cells = rows_in_mo[0].locator("td")
                        if cells.count() > loc_idx:
                            raw_loc = cell_text(cells.nth(loc_idx))
                            location_name = raw_loc.split(",", 1)[0].strip()
                            print(f"   Location (MO) = {location_name!r} (raw={raw_loc!r})")
                if not location_name:
                    location_name = loc_name_from_listing.split(",", 1)[0].strip()
                    print(f"   Location (fallback) = {location_name!r}")
            except Exception as e:
                print(f"   ⚠️  Could not read Location: {e}")
                location_name = loc_name_from_listing.split(",", 1)[0].strip()

            external_id_value = None
            try:
                ext_ref_header = page.locator("//*[contains(normalize-space(text()),'External Reference')]/ancestor::div[@role='button'][1]").first
                ext_ref_header.wait_for(state="visible", timeout=20000)
                if ext_ref_header.get_attribute("aria-expanded") != "true":
                    ext_ref_header.scroll_into_view_if_needed()
                    ext_ref_header.click(timeout=30000)
                    page.wait_for_timeout(2000)

                panel_id = ext_ref_header.get_attribute("aria-controls")
                ext_ref_panel = page.locator(f'//*[@id="{panel_id}"]')
                ext_ref_panel.wait_for(state="visible", timeout=20000)

                if ext_ref_panel.get_by_text("NO DATA AVAILABLE").count() > 0:
                    print(f"   PO {pid} -> No External Reference")
                else:
                    ext_headers_loc = ext_ref_panel.get_by_role("columnheader")
                    ext_headers_loc.first.wait_for(state="visible", timeout=20000)
                    ext_header_texts = [" ".join(h.split()) for h in ext_headers_loc.all_inner_texts()]

                    ext_id_idx = next((i for i, h in enumerate(ext_header_texts) if h.lower() == "external id"), None)
                    if ext_id_idx is not None:
                        data_rows = ext_ref_panel.get_by_role("row")
                        first_data_row = data_rows.nth(1) if data_rows.count() > 1 else ext_ref_panel.get_by_role("checkbox").first
                        external_id_value = first_data_row.get_by_role("cell").nth(ext_id_idx).inner_text().strip()
                        print(f"   PO {pid} -> External ID: {external_id_value}")
            except Exception as e:
                print(f"   ⚠️  Could not read External Reference for {pid}: {e}")

            if external_id_value:
                records_by_ext[external_id_value] = {
                    "activity_type": activity_type,
                    "location_name": location_name,
                }

            # ---------- RETURN TO LISTING PAGE ----------
            try:
                sub_project_breadcrumb = page.locator(
                    "xpath=//nav[@aria-label='breadcrumb']//span[normalize-space(text())='Sub Project']"
                ).first

                if sub_project_breadcrumb.count() > 0:
                    sub_project_breadcrumb.click(force=True)
                    print("      🔙 Navigated back to Sub Project listing.")
                else:
                    page.locator("nav[aria-label='breadcrumb'] li.MuiBreadcrumbs-li").nth(1).click()

                page.wait_for_timeout(3000)

                in_progress_sites_tab.wait_for(state="visible", timeout=15000)
                in_progress_sites_tab.click()
                page.wait_for_timeout(2000)
                refresh_button.wait_for(state="visible", timeout=15000)
                refresh_button.click()
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"   ⚠️  Could not return to listing: {e}")
                break

        except Exception as e:
            print(f"❌ PO {pid} failed: {e} — continuing with next PO")
            try:
                page.locator("nav[aria-label='breadcrumb'] li.MuiBreadcrumbs-li").nth(1).click()
                page.wait_for_timeout(2000)
                in_progress_sites_tab.click()
                page.wait_for_timeout(2000)
            except:
                break
            continue

    # ==========================================================
    # 5. WRITE OUTPUT
    # ==========================================================
    if not records_by_ext:
        raise AssertionError("No External ID was captured, nothing to export")

    external_id = list(records_by_ext.keys())
    records = {
        ext_id: {
            "activity_type": meta.get("activity_type", ""),
            "location_name": meta.get("location_name", ""),
        }
        for ext_id, meta in records_by_ext.items()
    }

    try:
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = {}

    existing_data["external_id"] = external_id
    existing_data["records"] = records

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2)

    print(f"[INFO] External ID written to cto-captures.json: {external_id}")
    print(f"[INFO] Records written to cto-captures.json: {json.dumps(records, indent=2)}")

    # ==========================================================
    # 6. CLEANUP
    # ==========================================================
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)