from playwright.sync_api import Playwright, sync_playwright
import json, re, sys, os, ast
from pathlib import Path
from datetime import datetime
# ============================================================
# CONFIG
# ============================================================
#customer_name = "Cholas13-283902_Site1"
#customer_name = sys.argv[1] if len(sys.argv) > 1 else "agana3"
PM_JSON_PATH = Path("cto-captures.json")   # <-- PM records source

def _clean(x):
    return str(x).strip().strip("[]()'\" \t\r\n")

def to_id_list(raw):
    if raw is None or raw == "" or raw == []:
        return []
    if isinstance(raw, (list, tuple)):
        return [c for c in (_clean(x) for x in raw) if c]
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            for parser in (json.loads, ast.literal_eval):   # JSON first, then Python-style ['a', 'b']
                try:
                    val = parser(s)
                    if isinstance(val, (list, tuple)):
                        return [c for c in (_clean(x) for x in val) if c]
                except Exception:
                    pass
        return [c for c in (_clean(p) for p in s.split(",")) if c]
    return [_clean(raw)]

def load_external_ids():
    try:
        cto_vars = json.loads(os.environ.get("CTO_VARS", "{}") or "{}")
    except Exception:
        cto_vars = {}
    raw = cto_vars.get("external_id")
    source = "CTO_VARS"
    if raw in (None, "", []):
        raw = '''{{store.external_id}}'''          # triple single quotes: stored value may contain double quotes
        source = "store.external_id"
        if raw.strip().startswith("{" + "{"):      # token was not substituted (e.g. running locally)
            raw = None
    if raw in (None, "", []) and os.path.exists("cto-captures.json"):
        with open("cto-captures.json") as f:
            raw = json.load(f).get("external_id")
        source = "cto-captures.json"
    ids = to_id_list(raw)
    print(f"External IDs ({source}): {ids}")
    if not ids:
        raise AssertionError("No external_id found (CTO_VARS, store, or cto-captures.json)")
    return ids

external_ids = load_external_ids()

# ============================================================
# LOAD PM RECORDS (cto-captures.json)
# ============================================================
def load_pm_records():
    if not PM_JSON_PATH.exists():
        print(f"⚠️  PM JSON not found at {PM_JSON_PATH} — PM comparison will be SKIPPED")
        return {}
    with open(PM_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", {}) if isinstance(data, dict) else {}
    print(f"[PM] Loaded {len(records)} record(s) from {PM_JSON_PATH.name}")
    return records


pm_records = load_pm_records()


# ============================================================
# USER INPUT
# ============================================================
# Values may be:
#   - a plain string   → exact match expected
#   - a set/list/tuple → ANY of the values passes validation
USER_INPUT = {
    "Wifi":                    {"Yes", "No"},
    "Vendor":                  {"Comcast", "AT&T", "Spectrum", "Charter (Spectrum)", "Sparklight/Cable One/New Wave", "Frontier DSL", "Sprint", "Bevcomm", "Verizon", "TDS Telecom", "Mediacom", "CenturyLink", "Cox", "Blue Valley Technologies", "Consolidated Communications", "Windstream", "Wave Broadband", "RCN", "Optimum", "Suddenlink", "Frontier Communications", "EarthLink", "HughesNet", "Viasat", "Rise Broadband", "Mediacom Communications", "AT&T Fiber", "Verizon Fios", "Xfinity", "Cox Communications", "Spectrum Internet", "Frontier Fiber", "Windstream Internet", "TDS Fiber", "RCN Internet", "Optimum Online", "Suddenlink Internet", "EarthLink DSL", "HughesNet Satellite", "Viasat Internet", "Rise Broadband Wireless"},
    "BridgeMode":              {"Yes", "No"},
    "MinDWSpeed":              {"10 Mbps", "11 Mbps", "18 Mbps", "20 Mbps", "25 Mbps", "26 Mbps", "40 Mbps", "45 Mbps", "50 Mbps", "51 Mbps", "55 Mbps", "60 Mbps", "61 Mbps", "75 Mbps", "90 Mbps", "100 Mbps", "101 Mbps", "105 Mbps", "106 Mbps", "115 Mbps", "150 Mbps", "155 Mbps", "156 Mbps", "200 Mbps", "201 Mbps", "250 Mbps", "300 Mbps", "400 Mbps", "500 Mbps", "600 Mbps", "750 Mbps", "800 Mbps", "940 Mbps", "1000 Mbps", "1250 Mbps", "2000 Mbps"},
    "contraMinUPSpeed":        {"1 Mbps", "2 Mbps", "5 Mbps", "6 Mbps", "7 Mbps", "8 Mbps", "10 Mbps", "15 Mbps", "20 Mbps", "25 Mbps", "30 Mbps", "35 Mbps", "50 Mbps", "51 Mbps", "75 Mbps", "100 Mbps", "101 Mbps", "200 Mbps", "201 Mbps", "250 Mbps", "300 Mbps", "400 Mbps", "500 Mbps", "1000 Mbps", "TBD"},
    "contraTransportType":     {"Fiber", "DSL", "HFC"},
    "contraDeviceAcquisation": {"BYOD", "Rental"},
    "contraEquipmentRental":   {"Yes", "No"},
    "IPQuantity":              {"1", "5", "13", "29", "61", "125", "253", ">253"},
    "IPVersion":               {"IPv4", "IPv6"},
}

KEY_TO_UI_NAME = {
    "Wifi":                    "Wi-Fi",
    "Vendor":                  "Service Provider",
    "BridgeMode":              "Bridge Mode",
    "MinDWSpeed":              "Min DW Speed",
    "contraMinUPSpeed":        "Min UP Speed",
    "contraTransportType":     "Transport Type",
    "contraDeviceAcquisation": "Device Acquisition Type",
    "contraEquipmentRental":   "Equipment Rental",
    "IPQuantity":              "Static IP Quantity",
    "IPVersion":               "Static IP Version",
}

STATUS_MAP = {
    "acknowledged": {"fo": "acknowledged", "poi": "acknowledged", "case": 1},
    "in progress":  {"fo": "in progress",  "poi": "in progress",  "case": 2},
    "completed":    {"fo": "completed",    "poi": "active",       "case": 3},
}


# ============================================================
# HELPERS
# ============================================================
def norm(s):
    return " ".join(str(s).strip().lower().split())


def col_index(headers, pattern):
    for i, h in enumerate(headers):
        if re.search(pattern, h, re.IGNORECASE):
            return i
    return None


def find_table_by_header(page, header_regex, timeout=5000):
    """Return first table whose ANY <th> inner_text matches header_regex."""
    import time
    deadline = time.time() + timeout / 1000.0
    while time.time() < deadline:
        for t in page.locator("table").all():
            try:
                heads = t.locator("th").all_inner_texts()
                if any(re.search(header_regex, h.strip(), re.IGNORECASE) for h in heads):
                    return t
            except Exception:
                continue
        page.wait_for_timeout(300)
    return None


def safe_input_value(locator):
    try:
        return locator.input_value().strip()
    except Exception:
        return ""


def get_field_by_label(page, label_text):
    """Return the input value associated with a label."""
    try:
        lbl = page.locator(f"label:has-text('{label_text}')").first
        if lbl.count() > 0:
            inp = lbl.locator("xpath=following::input[1]").first
            if inp.count() > 0:
                return safe_input_value(inp)
    except Exception:
        pass
    return ""


def get_om_location(page):
    """Read 'Location' from the Market Offering table."""
    raw = ""
    try:
        mo_tbl = find_table_by_header(page, r"Market Offering I[dD]", timeout=3000)
        if mo_tbl and mo_tbl.count() > 0:
            headers = [h.inner_text().strip().replace("\n", " ")
                       for h in mo_tbl.locator("thead th").all()]
            loc_idx = col_index(headers, r"Location")
            rows = mo_tbl.locator("tr:has(td)").all()
            if rows and loc_idx is not None:
                cells = rows[0].locator("td")
                if cells.count() > loc_idx:
                    raw = cells.nth(loc_idx).inner_text().strip()
    except Exception:
        pass
    return raw


def _parse_created_date(s):
    """
    Robust parser for OM Audit Log 'Created Date' values.

    Handles:
      14-10-2026 09:04:15:646545 AM   <- actual OM format (colon + AM/PM)
      14-10-2026 09:04:15.646545 AM
      14-10-2026 09:04:15 AM
      14-10-2026 09:04:15
      2026-10-14 09:04:15.646545
      2026-10-14 09:04:15
    Returns datetime or None.
    """
    if not s:
        return None

    raw = str(s).strip().rstrip(".").rstrip(",")

    ampm = None
    upper = raw.upper()
    if upper.endswith("AM"):
        ampm = "AM"
        raw = raw[:-2].strip()
    elif upper.endswith("PM"):
        ampm = "PM"
        raw = raw[:-2].strip()

    m = re.match(
        r"^(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})[:.](\d+)$",
        raw
    )
    normalized = None
    if m:
        dd, mm, yyyy, hh, mi, ss, micro = m.groups()
        micro = (micro + "000000")[:6]
        normalized = f"{dd}-{mm}-{yyyy} {hh}:{mi}:{ss}.{micro}"
    else:
        m2 = re.match(
            r"^(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})$",
            raw
        )
        if m2:
            dd, mm, yyyy, hh, mi, ss = m2.groups()
            normalized = f"{dd}-{mm}-{yyyy} {hh}:{mi}:{ss}.000000"
        else:
            m3 = re.match(
                r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})[:.](\d+)$",
                raw
            )
            if m3:
                yyyy, mm, dd, hh, mi, ss, micro = m3.groups()
                micro = (micro + "000000")[:6]
                normalized = f"{dd}-{mm}-{yyyy} {hh}:{mi}:{ss}.{micro}"

    if normalized is None:
        return None

    if ampm:
        try:
            return datetime.strptime(f"{normalized} {ampm}", "%d-%m-%Y %I:%M:%S.%f %p")
        except Exception:
            return None
    else:
        try:
            return datetime.strptime(normalized, "%d-%m-%Y %H:%M:%S.%f")
        except Exception:
            return None


def go_back_to_listing(page):
    """Return to the Product Orders listing page."""
    try:
        crumb = page.get_by_text("Product Orders", exact=True).first
        if crumb.count() > 0 and crumb.is_visible():
            crumb.click()
            page.wait_for_timeout(1500)
            page.locator("img[aria-label='Advanced Search']").wait_for(
                state="visible", timeout=15000
            )
            return True
    except Exception:
        pass

    try:
        page.goto("{{env.OM}}",
                  wait_until="domcontentloaded", timeout=20000)
        page.get_by_role("button", name="Orchestrator").wait_for(
            state="visible", timeout=15000
        )
        if page.locator("img[aria-label='Advanced Search']").count() == 0:
            page.get_by_role("button", name="Orchestrator").click()
            page.wait_for_timeout(1500)
        page.locator("img[aria-label='Advanced Search']").wait_for(
            state="visible", timeout=15000
        )
        return True
    except Exception:
        pass

    try:
        page.go_back()
        page.wait_for_timeout(1500)
        page.locator("img[aria-label='Advanced Search']").wait_for(
            state="visible", timeout=10000
        )
        return True
    except Exception:
        return False


# ============================================================
# PAYLOAD EXTRACTION
# ============================================================
def extract_payload_tree(root_locator):
    """
    Robust walker for jsen-edit-view.

    Handles two patterns:
      A) Simple leaf: nestedJson → [label(key)] → container → [label(value)]
      B) Wrapped leaf: nestedJson → [label(key)] → container →
           nestedJson(empty label) → container → [label(value)]
    """
    result = {}

    def read_value(container):
        """Read a scalar value from a container that has no nested children."""
        try:
            all_lbls = container.locator("label.jsonVal").all()
            for l in all_lbls:
                try:
                    t = l.inner_text().strip()
                    if t:
                        return t
                except Exception:
                    continue
        except Exception:
            pass
        try:
            inp = container.locator("input, textarea").first
            if inp.count() > 0:
                try:
                    return inp.input_value().strip()
                except Exception:
                    pass
        except Exception:
            pass
        return ""

    def has_nested_children(container):
        try:
            return container.locator(
                ":scope > div.nestedJson, "
                ":scope > div.MuiGrid-item > div.nestedJson, "
                ":scope > div.MuiGrid-container > div.nestedJson"
            ).count()
        except Exception:
            return 0

    def get_child_nesteds(container):
        try:
            return container.locator(
                ":scope > div.nestedJson, "
                ":scope > div.MuiGrid-item > div.nestedJson, "
                ":scope > div.MuiGrid-container > div.nestedJson"
            ).all()
        except Exception:
            return []

    def walk(nb, prefix):
        # 1. Key label of this node
        key = ""
        try:
            kl = nb.locator(":scope > label.jsonVal").first
            if kl.count() > 0:
                key = kl.inner_text().strip().rstrip(":")
        except Exception:
            key = ""

        node_path = f"{prefix}.{key}" if (prefix and key) else (key or prefix)

        # 2. Value container
        vc = None
        try:
            c = nb.locator(":scope > div.MuiGrid-container").first
            if c.count() > 0:
                vc = c
        except Exception:
            pass

        if vc is None:
            return

        n_children = has_nested_children(vc)

        # 3. Single nested child with EMPTY label → descend without
        #    adding to the path (wrapper pattern)
        if n_children == 1:
            only_child = get_child_nesteds(vc)[0]
            try:
                only_key = only_child.locator(
                    ":scope > label.jsonVal"
                ).first.inner_text().strip()
            except Exception:
                only_key = ""
            if not only_key:
                walk(only_child, node_path)
                return

        # 4. Recurse into each child nestedJson
        if n_children > 0:
            for ch in get_child_nesteds(vc):
                walk(ch, node_path)
            return

        # 5. Leaf — read scalar value
        val = read_value(vc)
        if node_path:
            if node_path not in result:
                result[node_path] = val

    # Entry: top-level nestedJson blocks
    top = root_locator.locator("div.nestedJson").all()
    for el in top:
        try:
            has_anc = el.evaluate(
                "el => { let p = el.parentElement; "
                "while (p) { if (p.classList && p.classList.contains('nestedJson')) "
                "return true; p = p.parentElement; } return false; }"
            )
            if has_anc:
                continue
            walk(el, "")
        except Exception:
            continue

    return result


def find_payload_value(payload, ui_name):
    """
    Match a UI field name against flat or dotted payload keys.
    Position-agnostic: only the leaf name matters.
    """
    target = ui_name.strip().rstrip(":").lower()
    for k, v in payload.items():
        if k.strip().rstrip(":").lower() == target:
            return v
    for k, v in payload.items():
        leaf = k.split(".")[-1].strip().rstrip(":").lower()
        if leaf == target:
            return v
    return None


def read_payload_from_dialog(page):
    """
    Assumes dialog already open. Expands any collapsed nodes,
    scrolls through content, extracts payload tree.
    """
    dialog = page.locator("div[role='dialog']").last
    dialog.wait_for(state="visible", timeout=10000)

    content = dialog.locator(".MuiDialogContent-root").first
    if content.count() == 0:
        content = dialog.locator("[class*='MuiDialogContent']").first
    if content.count() == 0:
        content = dialog

    # Expand any collapsed jsen nodes (aria-expanded=false toggles)
    try:
        toggles = dialog.locator("[aria-expanded='false']").all()
        for t in toggles[:80]:
            try:
                t.scroll_into_view_if_needed()
                t.click(timeout=800)
                page.wait_for_timeout(120)
            except Exception:
                pass
    except Exception:
        pass

    # Also click any jsen toggle arrows (svg icons)
    try:
        arrows = dialog.locator("svg.MuiSvgIcon-root").all()
        for a in arrows[:100]:
            try:
                a.scroll_into_view_if_needed()
                a.click(timeout=500)
                page.wait_for_timeout(80)
            except Exception:
                pass
    except Exception:
        pass

    # Scroll to bottom to force-render virtualized rows
    last_h = 0
    for _ in range(40):
        try:
            h = content.evaluate(
                "(el) => { el.scrollTop = el.scrollHeight; return el.scrollHeight; }"
            )
        except Exception:
            break
        if h == last_h:
            break
        last_h = h
        page.wait_for_timeout(300)

    # Scroll back to top
    try:
        content.evaluate("(el) => { el.scrollTop = 0; }")
        page.wait_for_timeout(300)
    except Exception:
        pass

    return extract_payload_tree(dialog)


# ============================================================
# MAIN
# ============================================================
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(60000)

    # ---------- Login ----------
    page.goto("https://productgateway-pog.excelacomcloud.net/om/")
    page.get_by_role("textbox", name="Username Password").wait_for(state="visible", timeout=30000)
    page.get_by_role("textbox", name="Username Password").fill("Arunselvakumar")
    page.locator("#password").fill("Welcome#1234")
    page.get_by_role("button", name="Login").click()

    page.get_by_role("button", name="Orchestrator").wait_for(state="visible", timeout=30000)
    page.get_by_role("button", name="Orchestrator").click()
    page.wait_for_timeout(1500)

    # ---------- Dynamic loop ----------
    total = len(external_ids)
    print(f"\n{'=' * 70}")
    print(f"  Orchestration Validation — {total} External ID(s) to process")
    print(f"{'=' * 70}")

    results = {}

    for i, ext_id in enumerate(external_ids, start=1):
        print(f"\n{'#' * 70}")
        print(f"# [{i}/{total}] POG: External ID {ext_id}")
        print(f"{'#' * 70}")

        rec = {"ext_id": ext_id}
        results[ext_id] = rec
    

        # ---------- 0. Close any lingering dialog ----------
        try:
            if page.locator("div[role='dialog']").count() > 0:
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # ---------- 0b. Return to listing ----------
        if i > 1:
            print("[nav] Returning to Product Orders listing ...")
            if not go_back_to_listing(page):
                print("❌ Could not return to listing page")
                rec["search"] = "FAIL"
                continue
            page.wait_for_timeout(1000)
        else:
            if page.locator("img[aria-label='Advanced Search']").count() == 0:
                print("[nav] Navigating to listing ...")
                if not go_back_to_listing(page):
                    print("❌ Could not reach listing page on first iteration")
                    rec["search"] = "FAIL"
                    continue
                page.wait_for_timeout(3000)

        # # ---------- 1. Advanced Search ----------
        # try:
        #     page.locator("img[aria-label='Advanced Search']").click()
        #     page.wait_for_timeout(1000)

        #     page.get_by_label("Customer Name").fill(customer_name)
        #     page.get_by_label("Save Search Name").fill(customer_name)
        #     page.locator("button.advancedsearch:has-text('SEARCH')").click()
        #     page.wait_for_timeout(2500)

        #     page.locator("tr:has(td)").first.wait_for(state="visible", timeout=15000)
        # except Exception as e:
        #     print(f"❌ Search failed for {ext_id}: {e}")
        #     rec["search"] = "FAIL"
        #     continue
        # page.wait_for_timeout(3000)

        # ---------- 2. Open matching order ----------
        target_row = page.locator("tr:has(td)").filter(has_text=ext_id).first
        try:
            target_row.wait_for(state="visible", timeout=15000)
        except Exception:
            rows_txt = page.locator("tr:has(td)").all_inner_texts()
            print(f"❌ External ID {ext_id} not found in {len(rows_txt)} result rows")
            for t in rows_txt[:10]:
                print("   ", " ".join(t.split()))
            rec["search"] = "FAIL"
            continue

        rec["search"] = "PASS"
        target_row.locator("span.hyperlink, a").first.click()
        page.wait_for_timeout(3000)

        # ---------- 3. Market Offering ----------
        print("\n--- Validating Market Offering ---")
        try:
            mo_table = find_table_by_header(page, r"Market Offering I[dD]", timeout=5000)
            if mo_table is None or mo_table.count() == 0:
                print("❌ Market Offering table not found")
                rec["market_offering"] = "FAIL"
            else:
                mo_table.scroll_into_view_if_needed()
                rows = mo_table.locator("tr:has(td)").all()
                if rows:
                    cells = rows[0].locator("td")
                    mo_id   = cells.nth(0).inner_text().strip()
                    mo_name = cells.nth(1).inner_text().strip()
                    mo_loc  = cells.nth(2).inner_text().strip()
                    print(f"✅ MO → ID={mo_id}, Name={mo_name}, Loc={mo_loc}")
                    rec["market_offering"] = "PASS"
                else:
                    print("❌ Market Offering table has no data rows")
                    rec["market_offering"] = "FAIL"
        except Exception as e:
            print(f"❌ Market Offering error: {e}")
            rec["market_offering"] = "FAIL"
            page.wait_for_timeout(1000)

        # ---------- 4. Fulfillment Order Grouping ----------
        print("\n--- Validating Fulfillment Order Grouping ---")
        fo_to_items = {}
        try:
            fo_table = find_table_by_header(page, r"Fulfillment Order I[dD]", timeout=5000)
            if fo_table is None or fo_table.count() == 0:
                print("❌ Fulfillment Order table not found")
                rec["fulfillment"] = "FAIL"
            else:
                fo_table.scroll_into_view_if_needed()
                page.wait_for_timeout(400)

                headers = [h.inner_text().strip().replace("\n", " ")
                           for h in fo_table.locator("thead th").all()]
                fo_id_idx     = col_index(headers, r"Fulfillment Order I[dD]")
                item_name_idx = col_index(headers, r"Product Order Item Name")

                if fo_id_idx is None or item_name_idx is None:
                    print(f"❌ Required columns missing. Headers={headers}")
                    rec["fulfillment"] = "FAIL"
                else:
                    for r in fo_table.locator("tr:has(td)").all():
                        cells = r.locator("td")
                        if cells.count() <= max(fo_id_idx, item_name_idx):
                            continue
                        fo_id = cells.nth(fo_id_idx).inner_text().strip()
                        name  = cells.nth(item_name_idx).inner_text().strip()
                        if fo_id and name:
                            fo_to_items.setdefault(fo_id, []).append(name)

                    print("📋 Fulfillment Order → Product Order Item Name:")
                    for fo_id, items in fo_to_items.items():
                        print(f"   {fo_id} → {items}")
                    rec["fulfillment"] = "PASS"
        except Exception as e:
            print(f"❌ Fulfillment Order error: {e}")
            rec["fulfillment"] = "FAIL"
            page.wait_for_timeout(1000)

        # ---------- 5. Cross-table mapping ----------
        print("\n--- Conditional Cross-Table Mapping ---")
        fo_items_set = set()
        for items in fo_to_items.values():
            fo_items_set.update(items)

        poi_items_set = set()
        try:
            poi_table = find_table_by_header(page, r"^Product Order Item I[dD]", timeout=3000)
            if poi_table and poi_table.count() > 0:
                poi_table.scroll_into_view_if_needed()
                headers = [h.inner_text().strip().replace("\n", " ")
                           for h in poi_table.locator("thead th").all()]
                name_idx = col_index(headers, r"Product Order Item Name")
                if name_idx is not None:
                    for r in poi_table.locator("tr:has(td)").all():
                        cells = r.locator("td")
                        if cells.count() > name_idx:
                            n = cells.nth(name_idx).inner_text().strip()
                            if n:
                                poi_items_set.add(n)
        except Exception as e:
            print(f"❌ POI table error: {e}")

        mo_names_set = set()
        try:
            mo_tbl = find_table_by_header(page, r"^Market Offering I[dD]", timeout=3000)
            if mo_tbl and mo_tbl.count() > 0:
                headers = [h.inner_text().strip().replace("\n", " ")
                           for h in mo_tbl.locator("thead th").all()]
                nidx = col_index(headers, r"Market Offering Name")
                if nidx is not None:
                    for r in mo_tbl.locator("tr:has(td)").all():
                        cells = r.locator("td")
                        if cells.count() > nidx:
                            n = cells.nth(nidx).inner_text().strip()
                            if n:
                                mo_names_set.add(n)
        except Exception:
            pass

        print(f"   FO items: {sorted(fo_items_set)}")
        print(f"   POI items: {sorted(poi_items_set)}")
        print(f"   MO names: {sorted(mo_names_set)}")

        rule_ok = True

        # Rule 1
        TRIGGER_1 = {"Managed Connectivity", "Site Access", "Site Access Plan",
                     "Business Internet", "Business Internet Plan"}
        if fo_items_set & TRIGGER_1:
            if "Internet Access" in poi_items_set:
                print("   ✅ Rule 1: FO triggers → 'Internet Access' present")
            else:
                print("   ❌ Rule 1: FO triggers but 'Internet Access' MISSING")
                rule_ok = False
        else:
            print("   ⏭️  Rule 1 not triggered")

        # Rule 2
        if "Equipment_CFS" in fo_items_set:
            if "Broadband Equipment" in poi_items_set:
                print("   ✅ Rule 2: 'Equipment_CFS' → 'Broadband Equipment' present")
            else:
                print("   ❌ Rule 2: 'Equipment_CFS' but 'Broadband Equipment' MISSING")
                rule_ok = False
        else:
            print("   ⏭️  Rule 2 not triggered")

        # Rule 3 — Static IP
        TRIGGER_3 = {"Static IP", "Static IP_CFS"}
        if fo_items_set & TRIGGER_3:
            if "Static IP Product" in poi_items_set:
                print("   ✅ Rule 3: 'Static IP'/'Static IP_CFS' → 'Static IP Product' present")
            else:
                print("   ❌ Rule 3: 'Static IP'/'Static IP_CFS' triggers but "
                      "'Static IP Product' MISSING")
                rule_ok = False
        else:
            print("   ⏭️  Rule 3 not triggered")

        # Rule 4
        if "Managed Broadband" in mo_names_set:
            if "Broadband Product" in poi_items_set:
                print("   ✅ Rule 4: 'Managed Broadband' → 'Broadband Product' present")
            else:
                print("   ❌ Rule 4: 'Managed Broadband' but 'Broadband Product' MISSING")
                rule_ok = False
        else:
            print("   ⏭️  Rule 4 not triggered")

        rec["cross_table"] = "PASS" if rule_ok else "FAIL"

        # ---------- 6. Status Mapping ----------
        print("\n--- Validating Status Mapping ---")
        status_ok = None
        parent_status = None
        try:
            lbl = page.locator("label:has-text('Status')").first
            if lbl.count() > 0:
                parent_status = lbl.locator("xpath=following::input[1]").first.input_value().strip()
        except Exception:
            pass

        if not parent_status:
            try:
                status_inp = page.locator("input[name='STATUS'], input[placeholder='Status']").first
                if status_inp.count() > 0:
                    parent_status = status_inp.input_value().strip()
            except Exception:
                pass

        if not parent_status:
            print("❌ Could not read Product Order → Status")
            rec["status_mapping"] = "FAIL"
        else:
            print(f"   Parent (Product Order → Status) = {parent_status!r}")
            key = norm(parent_status)

            if key not in STATUS_MAP:
                print(f"⚠️  Parent status {parent_status!r} not in STATUS_MAP")
                rec["status_mapping"] = "SKIP"
            else:
                rule         = STATUS_MAP[key]
                expected_fo  = rule["fo"]
                expected_poi = rule["poi"]
                case_no      = rule["case"]

                print(f"   → Case {case_no}: FO={expected_fo!r}, POI={expected_poi!r}")

                fo_rows_all = []
                try:
                    fo_table2 = find_table_by_header(page, r"^Fulfillment Order I[dD]", timeout=3000)
                    if fo_table2 and fo_table2.count() > 0:
                        fo_table2.scroll_into_view_if_needed()
                        headers = [h.inner_text().strip().replace("\n", " ")
                                   for h in fo_table2.locator("thead th").all()]
                        s_idx = col_index(headers, r"Order Status")
                        i_idx = col_index(headers, r"Fulfillment Order I[dD]")
                        if s_idx is not None:
                            for r in fo_table2.locator("tr:has(td)").all():
                                cells = r.locator("td")
                                if cells.count() <= s_idx:
                                    continue
                                st = cells.nth(s_idx).inner_text().strip()
                                fid = cells.nth(i_idx).inner_text().strip() if i_idx is not None else "?"
                                fo_rows_all.append((fid, st))
                except Exception as e:
                    print(f"❌ FO read error: {e}")

                poi_rows_all = []
                try:
                    poi_table2 = find_table_by_header(page, r"^Product Order Item I[dD]", timeout=3000)
                    if poi_table2 and poi_table2.count() > 0:
                        poi_table2.scroll_into_view_if_needed()
                        headers = [h.inner_text().strip().replace("\n", " ")
                                   for h in poi_table2.locator("thead th").all()]
                        s_idx = col_index(headers, r"Product Order Item State")
                        i_idx = col_index(headers, r"Product Order Item I[dD]")
                        if s_idx is not None:
                            for r in poi_table2.locator("tr:has(td)").all():
                                cells = r.locator("td")
                                if cells.count() <= s_idx:
                                    continue
                                st = cells.nth(s_idx).inner_text().strip()
                                iid = cells.nth(i_idx).inner_text().strip() if i_idx is not None else "?"
                                poi_rows_all.append((iid, st))
                except Exception as e:
                    print(f"❌ POI read error: {e}")

                fo_fail = poi_fail = 0
                fo_pass = poi_pass = 0

                print(f"\n   FO rows ({len(fo_rows_all)}):")
                for fid, st in fo_rows_all:
                    if norm(st) == expected_fo:
                        fo_pass += 1
                        print(f"      ✅ {fid:<15} → {st}")
                    else:
                        fo_fail += 1
                        print(f"      ❌ {fid:<15} → {st}  (expected {expected_fo!r})")

                print(f"\n   POI rows ({len(poi_rows_all)}):")
                for iid, st in poi_rows_all:
                    if norm(st) == expected_poi:
                        poi_pass += 1
                        print(f"      ✅ {iid:<15} → {st}")
                    else:
                        poi_fail += 1
                        print(f"      ❌ {iid:<15} → {st}  (expected {expected_poi!r})")

                if fo_fail == 0 and poi_fail == 0 and fo_pass > 0 and poi_pass > 0:
                    print(f"\n   ✅ Case {case_no} matched")
                    status_ok = True
                else:
                    print(f"\n   ❌ Case {case_no} FAILED")
                    status_ok = False

                rec["status_mapping"] = "PASS" if status_ok else "FAIL"

        # ---------- 7. Audit Log ----------
        print("\n--- Audit Log ---")
        audit_table = None
        try:
            audit_accordion = page.locator("div.MuiAccordionSummary-root").filter(
                has_text=re.compile("Audit Log", re.IGNORECASE)
            ).first
            if audit_accordion.count() > 0:
                audit_accordion.scroll_into_view_if_needed()
                page.wait_for_timeout(400)
                if audit_accordion.get_attribute("aria-expanded") == "false":
                    audit_accordion.click()
                    page.wait_for_timeout(1200)

            audit_table = find_table_by_header(page, r"Transaction ID", timeout=5000)

            if audit_table is None or audit_table.count() == 0:
                print("❌ Audit Log table not found")
                rec["audit_log"] = "FAIL"
            else:
                audit_table.scroll_into_view_if_needed()
                page.wait_for_timeout(400)

                try:
                    audit_table.locator("tr:has(td)").first.wait_for(state="visible", timeout=10000)
                except Exception:
                    print("⚠️  No audit rows appeared")

                headers = [h.inner_text().strip().replace("\n", " ")
                           for h in audit_table.locator("thead th").all()]
                idx_txn    = col_index(headers, r"Transaction ID")
                idx_svc    = col_index(headers, r"Service Name")
                idx_type   = col_index(headers, r"Transaction Type")
                idx_target = col_index(headers, r"Target System")
                idx_source = col_index(headers, r"Source System")

                audit_rows = audit_table.locator("tr:has(td)").all()
                if audit_rows:
                    for r in audit_rows:
                        cells = r.locator("td")
                        n = cells.count()

                        def cell(x):
                            return cells.nth(x).inner_text().strip() if (x is not None and x < n) else ""

                        print(f"   TxnID={cell(idx_txn):<20} "
                              f"Service={cell(idx_svc):<25} "
                              f"Type={cell(idx_type):<12} "
                              f"Target={cell(idx_target):<12} "
                              f"Source={cell(idx_source)}")
                    rec["audit_log"] = "PASS"
                else:
                    print("❌ No audit rows")
                    rec["audit_log"] = "FAIL"
        except Exception as e:
            print(f"❌ Audit Log error: {e}")
            rec["audit_log"] = "FAIL"


    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    print(f"\n{'=' * 70}")
    print(f"  FINAL SUMMARY — {total} External ID(s) processed")
    print(f"{'=' * 70}")

    SUMMARY_KEYS = (
            "search", "market_offering", "fulfillment", "cross_table",
            "status_mapping", "audit_log",
            "order_type_valid", "version_check",
            "activity_type_matches", "location_name_matches",
            "rev_history", "service_name_valid", "service_matches_type",
    )

    for ext_id, res in results.items():
        print(f"\nExternal ID {ext_id}:")
        for k in SUMMARY_KEYS:
            v = res.get(k, "—")
            mark = "✅" if v == "PASS" else ("❌" if v == "FAIL" else "⏭️")
            print(f"   {mark} {k:<20} : {v}")

    print(f"\n{'=' * 70}")
    all_pass = True
    for ext_id, res in results.items():
        for k in SUMMARY_KEYS:
            if res.get(k) == "FAIL":
                all_pass = False
                break

    print(f"OVERALL: {'✅ ALL PASSED' if all_pass else '❌ SOME FAILED'}")
    print(f"{'=' * 70}")

    context.close()
    browser.close()

    sys.exit(0 if all_pass else 1)


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)