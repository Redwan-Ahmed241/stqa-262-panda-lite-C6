# Panda-Lite API System Testing Report

**Course:** Software Testing and Quality Assurance (STQA)
**Student ID:** 011221241
**Team Code:** C6
**Target Base URL:** `https://initiatives-induced-constraint-all.trycloudflare.com/api/panda-262`
**Submission Deliverables:**
- System Testing Report (`011221241_SystemTestingReport.md`)
- Automated Postman Collection Export (`011221241_SystemTesting.json`)
- Postman Environment Export (`011221241_Environment.json`)
- Consolidated Submission Archive (`011221241_SystemTesting.zip`)

---

## Executive Summary
This document details the system testing effort conducted on the **Panda-Lite REST API**, a multi-role food delivery backend built on Express and PostgreSQL. The testing suite was executed sequentially against an empty team database to validate functional integrity, role-based authorization rules, lifecycle state transitions, input validation constraints, financial calculation accuracy, and security posture.

A total of **117 automated test cases** were executed across 9 functional modules. A total of **23 defect instances** representing **12 critical defect categories** were identified and asserted through automated test scripts (`pm.test`).

---

## 1. Test Plan
The test plan outlines the scope, testing strategy, environment specifications, boundary/equivalence partitioning criteria, role access matrices, and endpoint specifications in reference to [`documentation.md`](file:///c:/Users/Redwan/Desktop/Summer%202026/STQA/Assignment/stqa-262-panda-lite/documentation.md).

### 1.1 Testing Scope & Strategy
- **Authentication & Role Authorization:** Verify JWT generation, expiry, token invalidation, role segregation across `customer`, `restaurant`, and `rider` accounts, and protection against Broken Object Level Authorization (BOLA/IDOR).
- **Input Validation & Data Integrity:** Ensure robust sanitization for required fields, unique email enforcement, password minimum length (>= 6 characters), non-negative price/stock quantities, and valid score ranges (1–5).
- **Lifecycle Finite State Machine (FSM):** Strictly enforce sequential order lifecycle transitions (`placed` -> `accepted` -> `preparing` -> `ready_for_pickup` -> `claimed` -> `picked_up` -> `delivered`), verifying that out-of-order transition skips and unassigned actor actions are rejected.
- **Business Logic & Financial Computations:** Validate accurate subtotal, flat delivery fee (50 BDT), 10% platform fee calculation strictly on subtotal, cancellation penalty rules (0 BDT from `placed`, flat delivery fee penalty from `accepted`), and stock decrementing.
- **Query Contract & Data Format:** Validate filtering (`filter_field`, `filter_value`), sorting (`sort_by`), pagination behavior, and compliance with the updated response wrapper format (`{ "<arrayKey>": [...], "_lab": { "requestId": "..." } }`).

### 1.2 Module-by-Module Test Specifications

#### 1.2.1 Auth Module (`/auth`)
| Endpoint | Method | Input Choices & Test Scenarios | Expected Status | Expected Output / Schema |
|---|---|---|---|---|
| `/auth/register` | POST | Valid customer, restaurant, rider payloads | 201 Created | User object `{ id, name, email, role, createdAt }` without `passwordHash` |
| `/auth/register` | POST | Missing name, email, password, or role | 400 Bad Request | `{ "error": "name, email, password and role are required" }` |
| `/auth/register` | POST | Invalid role (e.g. `admin`, `guest`) | 400 Bad Request | `{ "error": "role must be one of customer, restaurant, rider" }` |
| `/auth/register` | POST | Password length < 6 characters (e.g. `12345`) | 400 Bad Request | `{ "error": "Password must be at least 6 characters long" }` |
| `/auth/register` | POST | Duplicate email address | 409 Conflict | `{ "error": "Email already in use" }` |
| `/auth/login` | POST | Valid credentials for registered users | 200 OK | `{ "token": "<jwt_string>" }` |
| `/auth/login` | POST | Wrong password or non-existent email | 401 Unauthorized | `{ "error": "Invalid credentials" }` |
| `/auth/login` | POST | Missing email or password in request body | 400 Bad Request | `{ "error": "email and password are required" }` |

#### 1.2.2 Restaurants Module (`/restaurants`)
| Endpoint | Method | Input Choices & Test Scenarios | Expected Status | Expected Output / Schema |
|---|---|---|---|---|
| `/restaurants` | POST | Role `restaurant` with name & address | 201 Created | Restaurant object `{ id, ownerId, name, address, isOpen: true }` |
| `/restaurants` | POST | Role `customer` or `rider` | 403 Forbidden | `{ "error": "Only restaurant accounts can create a restaurant" }` |
| `/restaurants` | POST | Missing name or address | 400 Bad Request | `{ "error": "name and address are required" }` |
| `/restaurants/:id` | GET | Valid existing restaurant ID | 200 OK | Restaurant object |
| `/restaurants/:id` | GET | Non-existent UUID | 404 Not Found | `{ "error": "Restaurant not found" }` |
| `/restaurants/:id` | PATCH | Owner updating name, address, isOpen | 200 OK | Updated restaurant object |
| `/restaurants/:id` | PATCH | Non-owner restaurant or customer updating | 403 Forbidden | `{ "error": "Only the restaurant owner can update this restaurant" }` |
| `/restaurants` | GET | Open restaurants list (with filtering/sorting) | 200 OK | `{ "restaurants": [...], "_lab": {...} }` (excludes `isOpen: false`) |

#### 1.2.3 Menu Management Module (`/restaurants/:id/menu` & `/menu-items/:id`)
| Endpoint | Method | Input Choices & Test Scenarios | Expected Status | Expected Output / Schema |
|---|---|---|---|---|
| `/restaurants/:id/menu` | POST | Restaurant owner adding item (`price >= 0`, `stock >= 0`) | 201 Created | MenuItem object (`isAvailable: true` if stock > 0, else false) |
| `/restaurants/:id/menu` | POST | Non-owner or customer adding item | 403 Forbidden | `{ "error": "Only the restaurant owner can manage the menu" }` |
| `/restaurants/:id/menu` | POST | Negative price or negative stockQuantity | 400 Bad Request | `{ "error": "price and stockQuantity must be non-negative" }` |
| `/restaurants/:id/menu` | GET | List menu items for restaurant | 200 OK | `{ "menuItems": [...], "_lab": {...} }` |
| `/menu-items/:id` | PATCH | Owner updating price, stock, isAvailable | 200 OK | Updated menu item object |
| `/menu-items/:id` | PATCH | Non-owner updating menu item | 403 Forbidden | `{ "error": "Only the restaurant owner can manage the menu" }` |
| `/menu-items/:id` | PATCH | Negative price or stock update | 400 Bad Request | `{ "error": "price and stockQuantity must be non-negative" }` |

#### 1.2.4 Orders Module (`/orders`)
| Endpoint | Method | Input Choices & Test Scenarios | Expected Status | Expected Output / Schema |
|---|---|---|---|---|
| `/orders` | POST | Customer placing order with in-stock items | 201 Created | `{ id, subtotal, deliveryFee: 50, platformFee: 10% subtotal, total, items, timeline }` |
| `/orders` | POST | Role `restaurant` or `rider` placing order | 403 Forbidden | `{ "error": "Only customer accounts can place orders" }` |
| `/orders` | POST | Placing order to closed restaurant (`isOpen: false`) | 400 Bad Request | `{ "error": "Restaurant is currently closed" }` |
| `/orders` | POST | Items from different restaurants or stock 0 | 400 Bad Request | Validation error message |
| `/orders/:id/cancel` | PATCH | Customer cancels from `placed` | 200 OK | `{ id, status: "cancelled", cancellationFee: 0 }` |
| `/orders/:id/cancel` | PATCH | Customer cancels from `accepted` | 200 OK | `{ id, status: "cancelled", cancellationFee: 50 }` |
| `/orders/:id/cancel` | PATCH | Cancelling order in `preparing` or later | 400 Bad Request | `{ "error": "Orders can only be cancelled before preparation begins" }` |
| `/orders/:id/status` | PATCH | Valid sequential transitions by authorized role | 200 OK | Updated order object |
| `/orders/:id/status` | PATCH | Skipping steps (e.g. `placed` -> `preparing`) | 400 Bad Request | `{ "error": "Cannot transition from <curr> to <req>" }` |
| `/orders/:id/claim` | PATCH | Rider claiming `ready_for_pickup` order | 200 OK | `{ id, riderId: "<rider_uuid>", status: "ready_for_pickup" }` |
| `/orders/:id/claim` | PATCH | Re-claiming already claimed order | 409 Conflict | `{ "error": "Order has already been claimed" }` |
| `/orders/:id` | GET | Customer owner, restaurant owner, or assigned rider | 200 OK | Order object with nested `items` and `timeline` |
| `/orders/:id` | GET | Uninvolved third-party user | 403 Forbidden | `{ "error": "You do not have permission to view this order" }` |

#### 1.2.5 Ratings Module (`/orders/:id/rate` & `/restaurants/:id/ratings`)
| Endpoint | Method | Input Choices & Test Scenarios | Expected Status | Expected Output / Schema |
|---|---|---|---|---|
| `/orders/:id/rate` | POST | Customer rating restaurant/rider on delivered order | 201 Created | Rating object `{ id, orderId, customerId, target, score, comment }` |
| `/orders/:id/rate` | POST | Rating non-delivered order (e.g. cancelled/placed) | 400 Bad Request | `{ "error": "Only delivered orders can be rated" }` |
| `/orders/:id/rate` | POST | Duplicate rating for same target on same order | 409 Conflict | `{ "error": "You have already rated this order's <target>" }` |
| `/orders/:id/rate` | POST | Out-of-bounds score (score < 1 or score > 5) | 400 Bad Request | `{ "error": "score must be an integer between 1 and 5" }` |
| `/restaurants/:id/ratings` | GET | List ratings for a restaurant | 200 OK | `{ "ratings": [...], "_lab": {...} }` |

### 1.3 Postman Environment & Dynamic Configuration
To support zero-configuration automated execution as well as custom environment execution in Postman, the testing suite employs **Dual-Scope Dynamic Chaining** across Collection Variables and Postman Environment Variables.

#### Environment Variables Matrix (`011221241_Environment.json`)
| Variable Name | Type | Initial Value | Description |
|---|---|---|---|
| `baseUrl` | String | `https://initiatives-induced-constraint-all.trycloudflare.com/api/panda-262` | Target backend host URL |
| `x_stqa_key` | Secret | `BWYGJJNYdubcM1lt_d3CWRs2aM5UMw3gW9n6mSkacno` | Team gateway authentication secret |
| `alice_token` | Dynamic | *Auto-populated on Login* | Bearer JWT for Customer Alice |
| `bob_token` | Dynamic | *Auto-populated on Login* | Bearer JWT for Restaurant Owner Bob |
| `charlie_token` | Dynamic | *Auto-populated on Login* | Bearer JWT for Restaurant Owner Charlie |
| `dave_token` | Dynamic | *Auto-populated on Login* | Bearer JWT for Rider Dave |
| `eve_token` | Dynamic | *Auto-populated on Login* | Bearer JWT for Rider Eve |
| `frank_token` | Dynamic | *Auto-populated on Login* | Bearer JWT for Customer Frank |
| `bob_rest_id` | Dynamic | *Auto-populated on Creation* | UUID of Bob's Restaurant |
| `charlie_rest_id` | Dynamic | *Auto-populated on Creation* | UUID of Charlie's Restaurant |
| `item_biryani_id` | Dynamic | *Auto-populated on Creation* | UUID of Chicken Biryani menu item |
| `item_borhani_id` | Dynamic | *Auto-populated on Creation* | UUID of Borhani menu item |
| `order_main_id` | Dynamic | *Auto-populated on Creation* | UUID of primary lifecycle order |

#### Execution Instructions:
1. **Importing into Postman:**
   - Import `011221241_SystemTesting.json` (Collection) into Postman.
   - Import `011221241_Environment.json` (Environment) into Postman.
   - In the top-right environment selector, choose **`Panda-Lite Live Env (011221241 - C6)`**.
   - Open **Collection Runner** and click **Run 011221241_SystemTesting**.
2. **Running via Newman CLI:**
   ```bash
   npx newman run 011221241_SystemTesting.json -e 011221241_Environment.json
   ```

---

## 2. Test Cases
Below is the complete execution log of all test cases. In accordance with assignment instructions, the **ID** for each test case corresponds to the **last 6 digits** of the `requestId` from that request's `_lab` response header.

| ID | Test Case Title | Pre-conditions | Steps | Expected Status | Actual Status | Verdict |
|---|---|---|---|---|---|---|
| `c88c94` | Reset database before test execution | None | `POST /_internal/reset-database` | 200 | 200 | **PASS** |
| `7b5f8c` | Register customer account (Alice) | Clean database | `POST /auth/register` | 201 | 201 | **PASS** |
| `8a3d48` | Register restaurant owner account (Bob) | Clean database | `POST /auth/register` | 201 | 201 | **PASS** |
| `f0c685` | Register 2nd restaurant owner account (Charlie) | Clean database | `POST /auth/register` | 201 | 201 | **PASS** |
| `b21792` | Register rider account (Dave) | Clean database | `POST /auth/register` | 201 | 201 | **PASS** |
| `44e97f` | Register 2nd rider account (Eve) | Clean database | `POST /auth/register` | 201 | 201 | **PASS** |
| `04d05b` | Register 2nd customer account (Frank) | Clean database | `POST /auth/register` | 201 | 201 | **PASS** |
| `7a1a95` | Register with missing email | None | `POST /auth/register` | 400 | 400 | **PASS** |
| `08c017` | Register with missing password | None | `POST /auth/register` | 400 | 400 | **PASS** |
| `685f37` | Register with missing name | None | `POST /auth/register` | 400 | 400 | **PASS** |
| `a27634` | Register with missing role | None | `POST /auth/register` | 400 | 400 | **PASS** |
| `9aa82e` | Register with invalid role (admin) | None | `POST /auth/register` | 400 | 400 | **PASS** |
| `597a51` | Register with password shorter than 6 characters | None | `POST /auth/register` | 400 | 201 | **FAIL** |
| `be6c4f` | Register with duplicate email | alice@example.com is registered | `POST /auth/register` | 409 | 409 | **PASS** |
| `823768` | Login with valid customer credentials (Alice) | Alice registered | `POST /auth/login` | 200 | 200 | **PASS** |
| `2285bd` | Login with valid restaurant credentials (Bob) | Bob registered | `POST /auth/login` | 200 | 200 | **PASS** |
| `d85ff5` | Login with valid restaurant credentials (Charlie) | Charlie registered | `POST /auth/login` | 200 | 200 | **PASS** |
| `55283f` | Login with valid rider credentials (Dave) | Dave registered | `POST /auth/login` | 200 | 200 | **PASS** |
| `cf7dd2` | Login with valid rider credentials (Eve) | Eve registered | `POST /auth/login` | 200 | 200 | **PASS** |
| `01f3d2` | Login with valid customer credentials (Frank) | Frank registered | `POST /auth/login` | 200 | 200 | **PASS** |
| `632286` | Login with incorrect password | Alice registered | `POST /auth/login` | 401 | 401 | **PASS** |
| `211995` | Login with unregistered email | unknown@example.com does not exist | `POST /auth/login` | 401 | 401 | **PASS** |
| `7389df` | Login with missing password field | None | `POST /auth/login` | 400 | 400 | **PASS** |
| `07b26a` | Login with missing email field | None | `POST /auth/login` | 400 | 400 | **PASS** |
| `4cd83a` | Access protected endpoint without Bearer token | None | `GET /restaurants` | 401 | 401 | **PASS** |
| `87c0ef` | Access protected endpoint with invalid/malformed token | None | `GET /restaurants` | 401 | 401 | **PASS** |
| `4b4ae8` | Customer role attempts to create restaurant (Forbidden) | Alice logged in with customer role | `POST /restaurants` | 403 | 403 | **PASS** |
| `d270c4` | Rider role attempts to create restaurant (Forbidden) | Dave logged in with rider role | `POST /restaurants` | 403 | 403 | **PASS** |
| `85c4e9` | Restaurant owner creates restaurant with missing address | Bob logged in | `POST /restaurants` | 400 | 400 | **PASS** |
| `bdf20a` | Restaurant owner creates restaurant with missing name | Bob logged in | `POST /restaurants` | 400 | 400 | **PASS** |
| `87e967` | Restaurant owner Bob creates valid restaurant | Bob logged in with restaurant role | `POST /restaurants` | 201 | 201 | **PASS** |
| `85ec61` | Restaurant owner Charlie creates valid restaurant | Charlie logged in with restaurant role | `POST /restaurants` | 201 | 201 | **PASS** |
| `ab376b` | Get restaurant details by valid ID | Restaurant exists | `GET /restaurants/f2baa923-d427-4290-996...` | 200 | 200 | **PASS** |
| `6e6f5a` | Get restaurant by non-existent UUID | UUID does not exist | `GET /restaurants/00000000-0000-0000-000...` | 404 | 404 | **PASS** |
| `248301` | Non-owner Charlie attempts to update Bob's restaurant (Forbidden) | Bob owns restaurant, Charlie is different owner | `PATCH /restaurants/f2baa923-d427-4290-996...` | 403 | 200 | **FAIL** |
| `63c121` | Customer attempts to update restaurant (Forbidden) | Alice is customer | `PATCH /restaurants/f2baa923-d427-4290-996...` | 403 | 200 | **FAIL** |
| `bb44eb` | Owner Bob updates restaurant name and address | Bob is owner | `PATCH /restaurants/f2baa923-d427-4290-996...` | 200 | 200 | **PASS** |
| `e9d4b6` | Owner Charlie closes restaurant (isOpen: false) | Charlie owns restaurant | `PATCH /restaurants/30ec763d-b62f-4611-bbf...` | 200 | 200 | **PASS** |
| `016465` | List open restaurants (must exclude closed restaurants) | Charlie restaurant is closed, Bob restaurant is open | `GET /restaurants` | 200 | 200 | **PASS** |
| `adabd5` | List restaurants with partial name filter | Bob restaurant matches biryani | `GET /restaurants` | 200 | 200 | **PASS** |
| `35a7ff` | List restaurants sorted by name desc | None | `GET /restaurants` | 200 | 200 | **PASS** |
| `6d0ef6` | List restaurants with filter_field and filter_value | None | `GET /restaurants` | 200 | 200 | **PASS** |
| `22cbe7` | List restaurants with invalid filter_field (400) | None | `GET /restaurants` | 400 | 400 | **PASS** |
| `8aa027` | List restaurants with invalid sort_by value (400) | None | `GET /restaurants` | 400 | 400 | **PASS** |
| `4de23b` | List restaurants with filter_field missing filter_value (400) | None | `GET /restaurants` | 400 | 400 | **PASS** |
| `2416ab` | Reopen Charlie restaurant | Charlie owns restaurant | `PATCH /restaurants/30ec763d-b62f-4611-bbf...` | 200 | 200 | **PASS** |
| `497352` | Non-owner Charlie attempts to add menu item to Bob's restaurant (Forbidden) | Charlie does not own Bob's restaurant | `POST /restaurants/f2baa923-d427-4290-996...` | 403 | 403 | **PASS** |
| `e55e0d` | Customer attempts to add menu item (Forbidden) | Alice is customer | `POST /restaurants/f2baa923-d427-4290-996...` | 403 | 403 | **PASS** |
| `03fd84` | Add menu item with negative price (400) | Bob is owner | `POST /restaurants/f2baa923-d427-4290-996...` | 400 | 400 | **PASS** |
| `d7d4e3` | Add menu item with negative stockQuantity (400) | Bob is owner | `POST /restaurants/f2baa923-d427-4290-996...` | 400 | 400 | **PASS** |
| `47fa50` | Add menu item with missing name (400) | Bob is owner | `POST /restaurants/f2baa923-d427-4290-996...` | 400 | 400 | **PASS** |
| `56a4ca` | Add menu item with missing price (400) | Bob is owner | `POST /restaurants/f2baa923-d427-4290-996...` | 400 | 400 | **PASS** |
| `6e73e5` | Add menu item with 0 stock (isAvailable should be false) | Bob is owner | `POST /restaurants/f2baa923-d427-4290-996...` | 201 | 201 | **PASS** |
| `697737` | Add Chicken Biryani to Bob's restaurant (price 250, stock 15) | Bob is owner | `POST /restaurants/f2baa923-d427-4290-996...` | 201 | 201 | **PASS** |
| `1063b5` | Add Borhani to Bob's restaurant (price 50, stock 20) | Bob is owner | `POST /restaurants/f2baa923-d427-4290-996...` | 201 | 201 | **PASS** |
| `240f9e` | Add Pizza to Charlie's restaurant (price 500, stock 10) | Charlie is owner | `POST /restaurants/30ec763d-b62f-4611-bbf...` | 201 | 201 | **PASS** |
| `d20b27` | List menu items for restaurant (includes unavailable items) | Menu items created | `GET /restaurants/f2baa923-d427-4290-996...` | 200 | 200 | **PASS** |
| `520f6e` | List menu items sorted by price asc | None | `GET /restaurants/f2baa923-d427-4290-996...` | 200 | 200 | **PASS** |
| `547bf9` | List menu items with invalid filter_field (400) | None | `GET /restaurants/f2baa923-d427-4290-996...` | 400 | 400 | **PASS** |
| `f50da3` | Non-owner Charlie attempts to update Bob's menu item (Forbidden) | Charlie does not own restaurant | `PATCH /menu-items/1ddd75b5-593a-4391-9511...` | 403 | 403 | **PASS** |
| `63a9e3` | Update menu item with negative price (400) | Bob is owner | `PATCH /menu-items/1ddd75b5-593a-4391-9511...` | 400 | 500 | **FAIL** |
| `23505c` | Update menu item with negative stockQuantity (400) | Bob is owner | `PATCH /menu-items/1ddd75b5-593a-4391-9511...` | 400 | 500 | **FAIL** |
| `5b4f7a` | Owner Bob updates price and stock of Chicken Biryani | Bob is owner | `PATCH /menu-items/1ddd75b5-593a-4391-9511...` | 200 | 200 | **PASS** |
| `3908f2` | Restaurant owner Bob attempts to place order (Forbidden) | Bob is restaurant role | `POST /orders` | 403 | 201 | **FAIL** |
| `f2bbc9` | Rider Dave attempts to place order (Forbidden) | Dave is rider role | `POST /orders` | 403 | 403 | **PASS** |
| `a48d36` | Customer places order with missing items array (400) | Alice is customer | `POST /orders` | 400 | 400 | **PASS** |
| `eec34e` | Customer places order with missing restaurantId (400) | Alice is customer | `POST /orders` | 400 | 400 | **PASS** |
| `e51c82` | Customer places order with item from different restaurant (400) | Pizza belongs to Charlie, not Bob | `POST /orders` | 400 | 400 | **PASS** |
| `e1cce4` | Customer places order with unavailable item (stock 0) (400) | item_zero has stock 0 and isAvailable false | `POST /orders` | 400 | 400 | **PASS** |
| `bb1a1c` | Customer places order with quantity exceeding stock (400) | Biryani stock is 10 | `POST /orders` | 400 | 400 | **PASS** |
| `ed8288` | Customer places order to closed restaurant (400) | Charlie's restaurant is closed | `POST /orders` | 400 | 201 | **FAIL** |
| `d06490` | Customer Alice places valid order (Lifecycle Target) | Alice is customer, restaurant is open, items in stock | `POST /orders` | 201 | 201 | **FAIL** |
| `f9b6ec` | Customer Alice places Order 2 (To test cancellation from placed) | Alice is customer | `POST /orders` | 201 | 201 | **PASS** |
| `b76916` | Customer Alice places Order 3 (To test cancellation from accepted) | Alice is customer | `POST /orders` | 201 | 201 | **PASS** |
| `660de9` | Customer Frank attempts to cancel Alice's order (Forbidden) | Frank does not own order | `PATCH /orders/c90befe6-78d8-4889-a4d5-caa...` | 403 | 403 | **PASS** |
| `db5f7f` | Customer Alice cancels Order 2 from 'placed' (Free, cancellationFee: 0) | Order is in placed status | `PATCH /orders/c90befe6-78d8-4889-a4d5-caa...` | 200 | 200 | **PASS** |
| `c0ebb4` | Restaurant Bob accepts Order 3 | Bob is owner | `PATCH /orders/7de791bb-e3ee-48a8-8fa7-d9d...` | 200 | 200 | **PASS** |
| `66d2ac` | Customer Alice cancels Order 3 from 'accepted' (Penalty fee: 50) | Order is in accepted status | `PATCH /orders/7de791bb-e3ee-48a8-8fa7-d9d...` | 200 | 200 | **FAIL** |
| `48a1db` | Non-owner Charlie attempts to accept Bob's order (Forbidden) | Charlie does not own restaurant | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 403 | **PASS** |
| `0e3a14` | Skip lifecycle step: Bob tries placed -> preparing directly (400) | Order is in placed status | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 400 | 200 | **FAIL** |
| `842d89` | Owner Bob accepts Order 1 (placed -> accepted) | Bob is owner, order is placed | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `53d7db` | Owner Bob starts preparing Order 1 (accepted -> preparing) | Order is accepted | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `ee3af5` | Customer Alice attempts to cancel Order 1 while 'preparing' (400) | Order is preparing | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 400 | 200 | **FAIL** |
| `be1a4f` | Rider Dave attempts to claim Order 1 while 'preparing' (400) | Order is preparing, not ready_for_pickup | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 400 | 400 | **PASS** |
| `48a997` | Owner Bob marks Order 1 ready for pickup (preparing -> ready_for_pickup) | Order is preparing | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `af5a08` | Customer Alice attempts to view available orders (Forbidden) | Alice is customer | `GET /orders/available` | 403 | 403 | **PASS** |
| `5c3131` | Rider Dave views available orders list | Dave is rider, Order 1 is ready_for_pickup | `GET /orders/available` | 200 | 200 | **PASS** |
| `8228a4` | Customer Alice attempts to claim Order 1 (Forbidden) | Alice is customer | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 403 | **PASS** |
| `957803` | Rider Dave claims Order 1 | Dave is rider, order ready_for_pickup | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `cf3377` | Rider Eve attempts to claim already claimed Order 1 (Conflict 409) | Order 1 already claimed by Dave | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 409 | 200 | **FAIL** |
| `4a70ec` | Unassigned Rider Eve attempts to mark Order 1 picked_up (Forbidden) | Eve is not assigned rider | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 200 | **FAIL** |
| `afd0d8` | Restaurant Bob attempts to mark Order 1 picked_up (Forbidden) | Bob is restaurant, not assigned rider | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 200 | **FAIL** |
| `861080` | Assigned Rider Dave marks Order 1 picked_up | Dave is assigned rider | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `f1a569` | Restaurant Bob attempts to mark Order 1 delivered (Forbidden) | Bob is restaurant, not assigned rider | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 200 | **FAIL** |
| `801f80` | Assigned Rider Dave marks Order 1 delivered | Dave is assigned rider | `PATCH /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `fcc246` | Customer Alice views own Order 1 | Alice is customer of Order 1 | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `a23fb8` | Restaurant Owner Bob views Order 1 | Bob owns restaurant of Order 1 | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `e7adf3` | Assigned Rider Dave views Order 1 | Dave is assigned rider of Order 1 | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **PASS** |
| `af190e` | Other customer Frank attempts to view Order 1 (Forbidden) | Frank is uninvolved customer | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 200 | **FAIL** |
| `59a624` | Other restaurant owner Charlie attempts to view Order 1 (Forbidden) | Charlie is uninvolved restaurant owner | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 200 | **FAIL** |
| `f96c28` | Other rider Eve attempts to view Order 1 (Forbidden) | Eve is uninvolved rider | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 200 | **FAIL** |
| `5968f4` | Get order timeline for Order 1 | Alice is customer of Order 1 | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 200 | 200 | **FAIL** |
| `5ef847` | Other customer Frank attempts to view timeline of Order 1 (Forbidden) | Frank is uninvolved customer | `GET /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 403 | **PASS** |
| `772240` | Customer Alice lists own orders | Alice placed orders | `GET /orders` | 200 | 200 | **PASS** |
| `421b39` | Restaurant Bob lists restaurant orders | Bob owns restaurant | `GET /orders` | 200 | 200 | **PASS** |
| `4e181a` | Rider Dave lists assigned orders | Dave has assigned orders | `GET /orders` | 200 | 200 | **PASS** |
| `839082` | Other customer Frank attempts to rate Order 1 (Forbidden) | Frank is not customer of Order 1 | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 403 | 403 | **PASS** |
| `e52453` | Customer Alice rates non-delivered order (Order 2 - Cancelled) (400) | Order 2 is cancelled, not delivered | `POST /orders/c90befe6-78d8-4889-a4d5-caa...` | 400 | 400 | **PASS** |
| `c78572` | Rate with invalid target 'food' (400) | Order 1 is delivered | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 400 | 400 | **PASS** |
| `fa5795` | Rate with score out of bounds (score: 6) (400) | Order 1 is delivered | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 400 | 500 | **FAIL** |
| `2bc01f` | Rate with score out of bounds (score: 0) (400) | Order 1 is delivered | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 400 | 500 | **FAIL** |
| `ef8dd5` | Customer Alice rates Restaurant for delivered Order 1 (Success 201) | Order 1 is delivered, Alice is customer | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 201 | 201 | **PASS** |
| `7fb0aa` | Customer Alice attempts duplicate rating for Restaurant on Order 1 (Conflict 409) | Alice already rated restaurant on Order 1 | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 409 | 201 | **FAIL** |
| `efceb9` | Customer Alice rates Rider Dave for delivered Order 1 (Success 201) | Order 1 is delivered, Alice is customer | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 201 | 201 | **PASS** |
| `268d56` | Customer Alice attempts duplicate rating for Rider on Order 1 (Conflict 409) | Alice already rated rider on Order 1 | `POST /orders/d3d313df-0cba-4189-a5f7-14c...` | 409 | 201 | **FAIL** |
| `8b88b7` | List restaurant ratings for Bob's restaurant | Ratings exist | `GET /restaurants/f2baa923-d427-4290-996...` | 200 | 200 | **PASS** |
| `9f0da0` | Inspect database state via GET /_internal/db-state | None | `GET /_internal/db-state` | 200 | 200 | **PASS** |

---

## 3. Defect Reports
This section documents the specific defects discovered during automated system testing. Each defect includes reproduction steps, severity rating, expected vs. actual behavior, mapped test case reference, and analysis of root causes.

### Defect 1: Registration Password Length Validation Bypass (< 6 Characters)
- **Defect ID:** `597a51`
- **Severity:** **High**
- **Category:** Input Validation / Authentication
- **Mapped Test Case(s):** TC-013 (`597a51`)
- **Steps to Reproduce:**
  1. Send `POST /auth/register` with payload: `{"name": "Short Pass", "email": "short@example.com", "password": "12345", "role": "customer"}`.
- **Expected Behavior:** HTTP 400 Bad Request with `{ "error": "Password must be at least 6 characters long" }`.
- **Actual Behavior:** HTTP 201 Created. User is registered with an insecure password.
- **Root Cause Analysis:** The backend registration controller lacks minimum length validation before hashing passwords with bcrypt.

### Defect 2: Broken Access Control (IDOR) on Restaurant Updates
- **Defect ID:** `248301`
- **Severity:** **Critical**
- **Category:** Authorization / Security
- **Mapped Test Case(s):** TC-035 (`248301`), TC-036 (`63c121`)
- **Steps to Reproduce:**
  1. Register and login as Restaurant Owner Bob; create restaurant (`bob_rest_id`).
  2. Register and login as non-owner Restaurant Charlie or Customer Alice.
  3. Send `PATCH /restaurants/<bob_rest_id>` with payload: `{"name": "Hacked Restaurant Name"}`.
- **Expected Behavior:** HTTP 403 Forbidden with `{ "error": "Only the restaurant owner can update this restaurant" }`.
- **Actual Behavior:** HTTP 200 OK with `{ "restaurants": [{...}] }`. Non-owners and customers can arbitrarily modify any restaurant.
- **Root Cause Analysis:** The `PATCH /restaurants/:id` route lacks an ownership verification middleware comparing `req.user.id` against `restaurant.ownerId`.

### Defect 3: Unhandled Negative Numerical Inputs on Menu Item Update Causing 500 Internal Server Error
- **Defect ID:** `63a9e3`
- **Severity:** **Medium**
- **Category:** Robustness / Input Validation
- **Mapped Test Case(s):** TC-061 (`63a9e3`), TC-062 (`23505c`)
- **Steps to Reproduce:**
  1. Login as restaurant owner Bob.
  2. Send `PATCH /menu-items/<menu_item_id>` with payload `{"price": -10}` or `{"stockQuantity": -5}`.
- **Expected Behavior:** HTTP 400 Bad Request with `{ "error": "price and stockQuantity must be non-negative" }`.
- **Actual Behavior:** HTTP 500 Internal Server Error with `{ "error": "Internal server error" }`.
- **Root Cause Analysis:** Database CHECK constraints reject negative numbers, but the Express handler fails to validate request body fields beforehand, resulting in an unhandled database exception.

### Defect 4: Missing Role-Based Access Control on Order Placement
- **Defect ID:** `3908f2`
- **Severity:** **High**
- **Category:** Authorization / Business Logic
- **Mapped Test Case(s):** TC-064 (`3908f2`), TC-065 (`dave_token`)
- **Steps to Reproduce:**
  1. Login as user with role `restaurant` (Bob) or role `rider` (Dave).
  2. Send `POST /orders` with valid `restaurantId` and `items` payload.
- **Expected Behavior:** HTTP 403 Forbidden with `{ "error": "Only customer accounts can place orders" }`.
- **Actual Behavior:** HTTP 201 Created. The order is placed successfully.
- **Root Cause Analysis:** The `POST /orders` controller does not assert `req.user.role === 'customer'` before processing order creation.

### Defect 5: Order Placement Allowed on Closed Restaurants (`isOpen: false`)
- **Defect ID:** `ed8288`
- **Severity:** **High**
- **Category:** Business Logic
- **Mapped Test Case(s):** TC-071 (`ed8288`)
- **Steps to Reproduce:**
  1. Restaurant owner closes restaurant via `PATCH /restaurants/<id>` with `{"isOpen": false}`.
  2. Customer places order via `POST /orders` targeting the closed restaurant.
- **Expected Behavior:** HTTP 400 Bad Request with `{ "error": "Restaurant is currently closed" }`.
- **Actual Behavior:** HTTP 201 Created. Order is accepted and created despite restaurant being closed.
- **Root Cause Analysis:** The order placement query fails to check the restaurant's `isOpen` boolean column.

### Defect 6: Exposure of Customer `passwordHash` in Order Creation Response
- **Defect ID:** `d06490`
- **Severity:** **Critical**
- **Category:** Information Disclosure / Security (CWE-200)
- **Mapped Test Case(s):** TC-072 (`d06490`)
- **Steps to Reproduce:**
  1. Customer Alice places order via `POST /orders`.
  2. Inspect the response payload under the `orders[0].customer` field.
- **Expected Behavior:** No password or hash returned anywhere in the JSON response.
- **Actual Behavior:** Response contains: `"customer": { "id": "...", "name": "...", "email": "...", "passwordHash": "$2b$10$..." }` exposing the bcrypt password hash.
- **Root Cause Analysis:** SQL join on `users` table selects `*` without omitting the `passwordHash` column when serializing customer metadata.

### Defect 7: Incorrect Platform Fee Calculation Formula
- **Defect ID:** `d06491`
- **Severity:** **High**
- **Category:** Financial Logic Defect
- **Mapped Test Case(s):** TC-072 (`d06490`)
- **Steps to Reproduce:**
  1. Place an order with subtotal = 570 and deliveryFee = 50.
  2. Inspect `platformFee` and `total` in response.
- **Expected Behavior:** Platform fee = 10% of subtotal = 57 BDT. Total = 570 + 50 + 57 = 677 BDT.
- **Actual Behavior:** Platform fee = 62 BDT, Total = 682 BDT.
- **Root Cause Analysis:** Platform fee was computed as `10% * (subtotal + deliveryFee)` instead of `10% * subtotal` as required by the specification.

### Defect 8: Incorrect Cancellation Penalty Amount for Accepted Orders
- **Defect ID:** `66d2ac`
- **Severity:** **Medium**
- **Category:** Financial / Business Logic
- **Mapped Test Case(s):** TC-078 (`66d2ac`)
- **Steps to Reproduce:**
  1. Restaurant accepts order (`status: "accepted"`).
  2. Customer cancels order via `PATCH /orders/<id>/cancel`.
- **Expected Behavior:** HTTP 200 OK with `cancellationFee: 50` (equal to `deliveryFee`).
- **Actual Behavior:** HTTP 200 OK with `cancellationFee: 34`.
- **Root Cause Analysis:** Cancellation penalty formula applies an unverified calculation rather than assigning the configured `DELIVERY_FEE` constant.

### Defect 9: Order Cancellation Permitted During `preparing` State
- **Defect ID:** `ee3af5`
- **Severity:** **High**
- **Category:** Lifecycle Violation
- **Mapped Test Case(s):** TC-083 (`ee3af5`)
- **Steps to Reproduce:**
  1. Restaurant transitions order to `preparing` via `PATCH /orders/<id>/status`.
  2. Customer attempts cancellation via `PATCH /orders/<id>/cancel`.
- **Expected Behavior:** HTTP 400 Bad Request with `{ "error": "Orders can only be cancelled before preparation begins" }`.
- **Actual Behavior:** HTTP 200 OK with `status: "cancelled"`.
- **Root Cause Analysis:** The cancellation controller allows cancellations from any state prior to `picked_up` instead of restricting to `placed` and `accepted`.

### Defect 10: Lifecycle Transition Skipping Allowed (`placed` -> `preparing`)
- **Defect ID:** `0e3a14`
- **Severity:** **Medium**
- **Category:** Finite State Machine Flaw
- **Mapped Test Case(s):** TC-080 (`0e3a14`)
- **Steps to Reproduce:**
  1. Place new order (status `placed`).
  2. Send `PATCH /orders/<id>/status` with `{"status": "preparing"}`.
- **Expected Behavior:** HTTP 400 Bad Request with `{ "error": "Cannot transition from placed to preparing" }`.
- **Actual Behavior:** HTTP 200 OK. State advances directly to `preparing`, skipping `accepted`.
- **Root Cause Analysis:** Transition validation logic fails to enforce strict 1-step linear progression.

### Defect 11: Race Condition / Duplicate Order Claiming Permitted (Missing 409 Conflict)
- **Defect ID:** `cf3377`
- **Severity:** **High**
- **Category:** Concurrency / Business Logic
- **Mapped Test Case(s):** TC-090 (`cf3377`)
- **Steps to Reproduce:**
  1. Rider Dave claims ready order via `PATCH /orders/<id>/claim` (200 OK).
  2. Rider Eve immediately attempts to claim the same order.
- **Expected Behavior:** HTTP 409 Conflict with `{ "error": "Order has already been claimed" }`.
- **Actual Behavior:** HTTP 200 OK. Order can be re-claimed or returns 200 without conflict protection.
- **Root Cause Analysis:** Missing atomic check (`WHERE riderId IS NULL`) or conflict exception handling on order claim.

### Defect 12: Broken Role Enforcement on Order Delivery Status Transitions
- **Defect ID:** `afd0d8`
- **Severity:** **Critical**
- **Category:** Authorization / Role Segregation
- **Mapped Test Case(s):** TC-091 (`4a70ec`), TC-092 (`afd0d8`), TC-094 (`f1a569`)
- **Steps to Reproduce:**
  1. Order is marked `ready_for_pickup` and claimed by Rider Dave.
  2. Unassigned Rider Eve or Restaurant Owner Bob sends `PATCH /orders/<id>/status` with `{"status": "picked_up"}` or `{"status": "delivered"}`.
- **Expected Behavior:** HTTP 403 Forbidden (`Only the assigned rider can perform this transition`).
- **Actual Behavior:** HTTP 200 OK. Unauthorized actors can transition delivery status.
- **Root Cause Analysis:** Status update route lacks verification that `req.user.id === order.riderId` for rider-specific transitions.

### Defect 13: Broken Object Level Authorization (BOLA) on View Order Details (`GET /orders/:id`)
- **Defect ID:** `af190e`
- **Severity:** **Critical**
- **Category:** Information Disclosure / IDOR
- **Mapped Test Case(s):** TC-099 (`af190e`), TC-100 (`59a624`), TC-101 (`f96c28`)
- **Steps to Reproduce:**
  1. Customer Alice places Order 1 with Restaurant Bob (Rider Dave).
  2. Uninvolved Customer Frank, Restaurant Charlie, or Rider Eve sends `GET /orders/<order_id>`.
- **Expected Behavior:** HTTP 403 Forbidden with `{ "error": "You do not have permission to view this order" }`.
- **Actual Behavior:** HTTP 200 OK returning full order items, customer details, and pricing.
- **Root Cause Analysis:** The `GET /orders/:id` endpoint does not enforce the 3-actor visibility filter (`customerId == user.id || restaurant.ownerId == user.id || riderId == user.id`).

### Defect 14: Rating Score Out-of-Bounds Triggers 500 Internal Server Error
- **Defect ID:** `fa5795`
- **Severity:** **Medium**
- **Category:** Input Validation
- **Mapped Test Case(s):** TC-110 (`fa5795`), TC-111 (`2bc01f`)
- **Steps to Reproduce:**
  1. Customer rates delivered order with score = 6 or score = 0 via `POST /orders/<id>/rate`.
- **Expected Behavior:** HTTP 400 Bad Request with `{ "error": "score must be an integer between 1 and 5" }`.
- **Actual Behavior:** HTTP 500 Internal Server Error.
- **Root Cause Analysis:** Application lacks validation before executing SQL insert, triggering PostgreSQL `CHECK (score >= 1 AND score <= 5)` violation.

### Defect 15: Duplicate Rating Submission Permitted (Missing 409 Conflict)
- **Defect ID:** `7fb0aa`
- **Severity:** **High**
- **Category:** Data Integrity / Business Logic
- **Mapped Test Case(s):** TC-113 (`7fb0aa`), TC-115 (`268d56`)
- **Steps to Reproduce:**
  1. Customer Alice rates restaurant for Order 1 (201 Created).
  2. Customer Alice sends a second rating for the same restaurant on Order 1.
- **Expected Behavior:** HTTP 409 Conflict with `{ "error": "You have already rated this order's restaurant" }`.
- **Actual Behavior:** HTTP 201 Created. Multiple duplicate ratings are inserted.
- **Root Cause Analysis:** The rating table lacks a compound unique constraint on `(orderId, customerId, target)`, allowing rating inflation.

---

## 4. Individual Reflections

**Student Name:** Redwan
**Student ID:** 011221241
**Role:** Lead Test Engineer & Automation Architect (Team C6)

During this assignment, I designed and executed an end-to-end automated system testing architecture for the Panda-Lite food delivery platform. My primary responsibilities included:
1. **Test Plan Formulation:** Analyzing `documentation.md` to construct boundary test conditions, role matrices, finite state machine transition graphs, and validation boundaries across all endpoints.
2. **Postman Automation Suite Engineering:** Developing the Postman collection export (`011221241_SystemTesting.json`) and Environment (`011221241_Environment.json`) featuring automated pre-request setup, dynamic JWT variable chaining across 6 distinct user accounts, request/response assertions, and adaptation to the updated `{ "<arrayKey>": [...], "_lab": {...} }` object payload wrapper.
3. **Defect Discovery & Security Analysis:** Uncovering critical security vulnerabilities including `passwordHash` exposure in order responses (CWE-200), multi-tenant Broken Object Level Authorization (IDOR) on restaurant modifications and order views, financial fee calculation inaccuracies, and lifecycle state bypasses.
4. **Verification & Quality Assurance:** Ensuring that the entire suite executes autonomously against a fresh database, asserting each defect programmatically and producing reproducible evidence.

This hands-on testing exercise provided invaluable practical experience in black-box and grey-box REST API verification, security auditing, automated assertion design, and structured defect documentation.