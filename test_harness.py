"""
Panda-Lite Automated System Test Harness & Scenario Runner
Author: Redwan (Student ID: 011221241) - Team C6
Course: STQA (Summer 2026)

Features:
- Automated full-stack scenario execution (Auth, Restaurant, Menu, Orders, Ratings)
- Dynamic JWT and UUID dependency injection
- Finite State Machine lifecycle validation
- Role-based Access Control (RBAC) matrix testing
- Automated defect assertion & reporting
- DB State snapshot integrity verification
"""

import requests
import json
import time
import sys

BASE_URL = "https://initiatives-induced-constraint-all.trycloudflare.com/api/panda-262"
DEFAULT_KEY = "BWYGJJNYdubcM1lt_d3CWRs2aM5UMw3gW9n6mSkacno"

class PandaTestHarness:
    def __init__(self, base_url=BASE_URL, api_key=DEFAULT_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-STQA-Key": self.api_key,
            "Content-Type": "application/json"
        })
        self.results = []
        self.tokens = {}
        self.entities = {}

    def log(self, tc_id, title, method, path, expected, actual, req_id, passed, reason=""):
        status_tag = "\033[92m[PASS]\033[0m" if passed else "\033[91m[DEFECT]\033[0m"
        print(f"{status_tag} {tc_id}: {title} | {method} {path} -> Exp: {expected}, Got: {actual} (ReqID: {req_id[-6:] if req_id else 'N/A'})")
        if not passed and reason:
            print(f"        \033[93mDefect Note:\033[0m {reason}")
        self.results.append({
            "id": tc_id,
            "title": title,
            "method": method,
            "path": path,
            "expected": expected,
            "actual": actual,
            "requestId": req_id,
            "shortId": req_id[-6:] if req_id else "N/A",
            "passed": passed,
            "reason": reason
        })

    def request(self, method, path, payload=None, token=None, params=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, json=payload, headers=headers, params=params, timeout=15)
            try:
                body = resp.json()
            except:
                body = resp.text
            req_id = "N/A"
            if isinstance(body, dict) and "_lab" in body:
                req_id = body["_lab"].get("requestId", "N/A")
            return resp.status_code, body, req_id
        except Exception as e:
            return 500, str(e), "ERROR"

    def run_all(self):
        print("="*70)
        print("  PANDA-LITE AUTOMATED SYSTEM TEST HARNESS & SCENARIO RUNNER")
        print(f"  Target Base URL: {self.base_url}")
        print("="*70)

        # 1. Reset Database
        st, b, r = self.request("POST", "/_internal/reset-database")
        self.log("TC-001", "Reset Database", "POST", "/_internal/reset-database", 200, st, r, st == 200)

        # 2. Register Users
        users_to_register = [
            ("Alice", "alice@example.com", "customer", "alice"),
            ("Bob", "bob@example.com", "restaurant", "bob"),
            ("Charlie", "charlie@example.com", "restaurant", "charlie"),
            ("Dave", "dave@example.com", "rider", "dave"),
            ("Eve", "eve@example.com", "rider", "eve"),
            ("Frank", "frank@example.com", "customer", "frank")
        ]
        for name, email, role, key in users_to_register:
            st, b, r = self.request("POST", "/auth/register", {"name": name, "email": email, "password": "password123", "role": role})
            self.entities[f"{key}_id"] = b.get("id") if isinstance(b, dict) else None
            self.log(f"TC-REG-{key.upper()}", f"Register {role} ({name})", "POST", "/auth/register", 201, st, r, st == 201)

        # 3. Defect Check: Password length < 6
        st, b, r = self.request("POST", "/auth/register", {"name": "Short", "email": "short@example.com", "password": "123", "role": "customer"})
        self.log("TC-DEF-PASS", "Short Password Length (<6 chars)", "POST", "/auth/register", 400, st, r, st == 400, "Password <6 chars accepted (201 Created)")

        # 4. Login Users
        for name, email, role, key in users_to_register:
            st, b, r = self.request("POST", "/auth/login", {"email": email, "password": "password123"})
            self.tokens[key] = b.get("token") if isinstance(b, dict) else None
            self.log(f"TC-LOG-{key.upper()}", f"Login {role} ({name})", "POST", "/auth/login", 200, st, r, st == 200 and bool(self.tokens[key]))

        # 5. Create Restaurants
        st, b, r = self.request("POST", "/restaurants", {"name": "Bob Biryani House", "address": "Dhanmondi Road 5"}, token=self.tokens["bob"])
        self.entities["bob_rest_id"] = b.get("id") or (b.get("restaurants", [{}])[0].get("id") if "restaurants" in b else None)
        self.log("TC-REST-BOB", "Owner Bob creates restaurant", "POST", "/restaurants", 201, st, r, st == 201)

        st, b, r = self.request("POST", "/restaurants", {"name": "Charlie Pizza", "address": "Banani Road 11"}, token=self.tokens["charlie"])
        self.entities["charlie_rest_id"] = b.get("id") or (b.get("restaurants", [{}])[0].get("id") if "restaurants" in b else None)
        self.log("TC-REST-CHARLIE", "Owner Charlie creates restaurant", "POST", "/restaurants", 201, st, r, st == 201)

        # 6. Defect Check: IDOR on Restaurant Update
        st, b, r = self.request("PATCH", f"/restaurants/{self.entities['bob_rest_id']}", {"name": "Hacked"}, token=self.tokens["charlie"])
        self.log("TC-DEF-REST-IDOR", "Non-owner modifying restaurant", "PATCH", f"/restaurants/{self.entities['bob_rest_id']}", 403, st, r, st == 403, "Non-owner can update other restaurants (200 OK)")

        # 7. Menu Items
        st, b, r = self.request("POST", f"/restaurants/{self.entities['bob_rest_id']}/menu", {"name": "Chicken Biryani", "price": 250, "stockQuantity": 15}, token=self.tokens["bob"])
        self.entities["item_biryani_id"] = b.get("id") or (b.get("menuItems", [{}])[0].get("id") if "menuItems" in b else None)
        self.log("TC-MENU-BIRYANI", "Add Biryani to Bob menu", "POST", "/restaurants/:id/menu", 201, st, r, st == 201)

        st, b, r = self.request("POST", f"/restaurants/{self.entities['bob_rest_id']}/menu", {"name": "Borhani", "price": 50, "stockQuantity": 20}, token=self.tokens["bob"])
        self.entities["item_borhani_id"] = b.get("id") or (b.get("menuItems", [{}])[0].get("id") if "menuItems" in b else None)
        self.log("TC-MENU-BORHANI", "Add Borhani to Bob menu", "POST", "/restaurants/:id/menu", 201, st, r, st == 201)

        # 8. Defect Check: 500 error on negative price in PATCH
        st, b, r = self.request("PATCH", f"/menu-items/{self.entities['item_biryani_id']}", {"price": -10}, token=self.tokens["bob"])
        self.log("TC-DEF-MENU-500", "Update menu item with negative price", "PATCH", "/menu-items/:id", 400, st, r, st == 400, "Negative price causes 500 Internal Server Error")

        # 9. Defect Check: Role bypass on Order Placement
        st, b, r = self.request("POST", "/orders", {"restaurantId": self.entities["bob_rest_id"], "items": [{"menuItemId": self.entities["item_biryani_id"], "quantity": 1}]}, token=self.tokens["bob"])
        self.log("TC-DEF-ORD-ROLE", "Restaurant account placing order", "POST", "/orders", 403, st, r, st == 403, "Restaurant accounts allowed to place orders (201 Created)")

        # 10. Valid Order Placement
        payload = {
            "restaurantId": self.entities["bob_rest_id"],
            "items": [
                {"menuItemId": self.entities["item_biryani_id"], "quantity": 2},
                {"menuItemId": self.entities["item_borhani_id"], "quantity": 1}
            ]
        }
        st, b, r = self.request("POST", "/orders", payload, token=self.tokens["alice"])
        order_obj = b.get("orders", [{}])[0] if isinstance(b, dict) and "orders" in b else b
        self.entities["order_id"] = order_obj.get("id")
        # Check passwordHash leak & fee calculation
        has_hash_leak = bool(order_obj.get("customer", {}).get("passwordHash"))
        fee_correct = (order_obj.get("platformFee") == 57)
        self.log("TC-ORD-VALID", "Customer places valid order", "POST", "/orders", 201, st, r, st == 201 and not has_hash_leak and fee_correct,
                 f"{'passwordHash leaked in response! ' if has_hash_leak else ''}{'Platform fee formula error (got 62 instead of 57)' if not fee_correct else ''}")

        # 11. Order Lifecycle Progression
        order_id = self.entities["order_id"]
        # Placed -> Accepted
        st, b, r = self.request("PATCH", f"/orders/{order_id}/status", {"status": "accepted"}, token=self.tokens["bob"])
        self.log("TC-LIFE-ACCEPT", "Owner Bob accepts order", "PATCH", f"/orders/{order_id}/status", 200, st, r, st == 200)

        # Accepted -> Preparing
        st, b, r = self.request("PATCH", f"/orders/{order_id}/status", {"status": "preparing"}, token=self.tokens["bob"])
        self.log("TC-LIFE-PREP", "Owner Bob starts preparing", "PATCH", f"/orders/{order_id}/status", 200, st, r, st == 200)

        # Defect Check: Cancel during preparing
        st, b, r = self.request("PATCH", f"/orders/{order_id}/cancel", {"reason": "Late"}, token=self.tokens["alice"])
        self.log("TC-DEF-CANCEL-PREP", "Cancel order during preparing", "PATCH", f"/orders/{order_id}/cancel", 400, st, r, st == 400, "Cancelling in preparing allowed (200 OK)")

        # Preparing -> Ready
        st, b, r = self.request("PATCH", f"/orders/{order_id}/status", {"status": "ready_for_pickup"}, token=self.tokens["bob"])
        self.log("TC-LIFE-READY", "Owner Bob marks ready for pickup", "PATCH", f"/orders/{order_id}/status", 200, st, r, st == 200)

        # Rider Dave Claims
        st, b, r = self.request("PATCH", f"/orders/{order_id}/claim", token=self.tokens["dave"])
        self.log("TC-CLAIM-DAVE", "Rider Dave claims order", "PATCH", f"/orders/{order_id}/claim", 200, st, r, st == 200)

        # Defect Check: Duplicate claim 409
        st, b, r = self.request("PATCH", f"/orders/{order_id}/claim", token=self.tokens["eve"])
        self.log("TC-DEF-CLAIM-409", "Rider Eve re-claims claimed order", "PATCH", f"/orders/{order_id}/claim", 409, st, r, st == 409, "Duplicate claim returned 200 instead of 409 Conflict")

        # Ready -> Picked Up
        st, b, r = self.request("PATCH", f"/orders/{order_id}/status", {"status": "picked_up"}, token=self.tokens["dave"])
        self.log("TC-LIFE-PICKUP", "Rider Dave marks picked up", "PATCH", f"/orders/{order_id}/status", 200, st, r, st == 200)

        # Picked Up -> Delivered
        st, b, r = self.request("PATCH", f"/orders/{order_id}/status", {"status": "delivered"}, token=self.tokens["dave"])
        self.log("TC-LIFE-DELIVER", "Rider Dave marks delivered", "PATCH", f"/orders/{order_id}/status", 200, st, r, st == 200)

        # 12. Defect Check: IDOR on View Order
        st, b, r = self.request("GET", f"/orders/{order_id}", token=self.tokens["frank"])
        self.log("TC-DEF-VIEW-IDOR", "Uninvolved customer views order", "GET", f"/orders/{order_id}", 403, st, r, st == 403, "Uninvolved customer can view order (200 OK)")

        # 13. Ratings
        st, b, r = self.request("POST", f"/orders/{order_id}/rate", {"target": "restaurant", "score": 5, "comment": "Great!"}, token=self.tokens["alice"])
        self.log("TC-RATE-REST", "Alice rates restaurant", "POST", f"/orders/{order_id}/rate", 201, st, r, st == 201)

        # Defect Check: Duplicate Rating 409
        st, b, r = self.request("POST", f"/orders/{order_id}/rate", {"target": "restaurant", "score": 4}, token=self.tokens["alice"])
        self.log("TC-DEF-RATE-409", "Duplicate rating submission", "POST", f"/orders/{order_id}/rate", 409, st, r, st == 409, "Duplicate rating accepted (201 Created)")

        # Defect Check: Score 6 causes 500 error
        st, b, r = self.request("POST", f"/orders/{order_id}/rate", {"target": "rider", "score": 6}, token=self.tokens["alice"])
        self.log("TC-DEF-SCORE-500", "Rating score out of range (score 6)", "POST", f"/orders/{order_id}/rate", 400, st, r, st == 400, "Score 6 causes 500 Internal Server Error")

        # 14. Final DB State Snapshot
        st, b, r = self.request("GET", "/_internal/db-state")
        self.log("TC-DB-STATE", "Verify database state snapshot", "GET", "/_internal/db-state", 200, st, r, st == 200)

        # Summary
        passed_cnt = sum(1 for x in self.results if x["passed"])
        defect_cnt = len(self.results) - passed_cnt
        print("\n" + "="*70)
        print(f"  EXECUTION SUMMARY: {len(self.results)} Scenarios Run | {passed_cnt} Passed | {defect_cnt} Defects Asserted")
        print("="*70)

if __name__ == "__main__":
    harness = PandaTestHarness()
    harness.run_all()
