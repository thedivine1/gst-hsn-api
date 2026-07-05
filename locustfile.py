"""
GST Accelerator API — Locust Load Test
=======================================
Usage:
  locust -f locustfile.py --host https://gstaccelerator.in
  locust -f locustfile.py --host https://gstaccelerator.in --headless -u 50 -r 5 --run-time 60s

Tip: Set API_KEY env var to test with a real key:
  set API_KEY=gsta_xxxx && locust -f locustfile.py --host https://gstaccelerator.in
"""

import os
import random
from locust import HttpUser, task, between

API_KEY = os.environ.get("API_KEY", "gsta_demo_frontend")

# Realistic product/service searches to simulate real developer usage
DESCRIPTIONS = [
    "basmati rice",
    "AC unit",
    "mobile phone",
    "gold jewellery",
    "cotton shirt",
    "footwear",
    "laptop",
    "medicine",
    "solar panel",
    "cement",
    "iron ore",
    "plastic bottle",
    "cooking oil",
    "electric vehicle",
    "software development services",
]

HSN_CODES = [
    "84151010",  # AC - Split system
    "10063012",  # Basmati rice
    "71131910",  # Gold jewellery
    "85171200",  # Mobile phones
    "61051000",  # Cotton shirt
    "64021900",  # Footwear
    "84713010",  # Laptops
]

SAC_CODES = [
    "997212",   # Real estate services
    "998314",   # IT software development
    "996311",   # Hotel accommodation
    "997221",   # Construction of residential buildings
]

SUPPLY_TYPES = ["intrastate", "interstate"]


class DeveloperUser(HttpUser):
    """
    Simulates a developer integrating the GST Accelerator API into their ERP/billing system.
    Mix of description lookups (most common), direct code lookups, and bulk requests.
    """
    wait_time = between(1, 3)
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

    @task(4)
    def lookup_by_description(self):
        """Most common use-case: search by product description"""
        desc = random.choice(DESCRIPTIONS)
        self.client.post(
            "/api/v1/lookup",
            json={"description": desc},
            headers=self.headers,
            name="/api/v1/lookup [POST simple]"
        )

    @task(2)
    def lookup_with_conditions(self):
        """Advanced lookup with condition flags (branded B2C with price threshold)"""
        self.client.post(
            "/api/v1/lookup",
            json={
                "description": random.choice(DESCRIPTIONS),
                "branded": random.choice([True, False]),
                "b2b": random.choice([True, False]),
                "sale_value_inr": random.choice([250, 500, 1000, 2500, 7500, 15000]),
                "supply_type": random.choice(SUPPLY_TYPES),
            },
            headers=self.headers,
            name="/api/v1/lookup [POST with conditions]"
        )

    @task(3)
    def hsn_exact_lookup(self):
        """Direct HSN code lookup — typical for ERP/billing integrations"""
        code = random.choice(HSN_CODES)
        self.client.get(
            f"/api/v1/hsn/{code}",
            headers=self.headers,
            name="/api/v1/hsn/{code}"
        )

    @task(1)
    def sac_exact_lookup(self):
        """SAC code lookup for service businesses"""
        code = random.choice(SAC_CODES)
        self.client.get(
            f"/api/v1/sac/{code}",
            headers=self.headers,
            name="/api/v1/sac/{code}"
        )

    @task(2)
    def get_lookup_alias(self):
        """GET alias for lookup — used by simple integrations and browser clients"""
        desc = random.choice(DESCRIPTIONS).replace(" ", "+")
        self.client.get(
            f"/api/v1/lookup?q={desc}",
            headers=self.headers,
            name="/api/v1/lookup [GET alias]"
        )

    @task(1)
    def autocomplete(self):
        """Autocomplete as user types in a search box"""
        prefix = random.choice(["bas", "gold", "cot", "mob", "foo", "cem", "sol"])
        self.client.get(
            f"/api/v1/autocomplete?q={prefix}",
            headers=self.headers,
            name="/api/v1/autocomplete"
        )

    @task(1)
    def bulk_lookup(self):
        """Batch lookup — used for spreadsheet / CSV processing flows"""
        items = random.sample(DESCRIPTIONS, k=random.randint(2, 5))
        self.client.post(
            "/api/v1/bulk",
            json=[{"description": d} for d in items],
            headers=self.headers,
            name="/api/v1/bulk [POST]"
        )

    @task(1)
    def health_check(self):
        """Infrastructure monitoring ping"""
        self.client.get("/api/v1/health", name="/api/v1/health")

    @task(1)
    def demo_widget(self):
        """Simulates the landing page demo widget (no key required)"""
        desc = random.choice(DESCRIPTIONS).replace(" ", "+")
        self.client.get(
            f"/api/demo/lookup?q={desc}",
            name="/api/demo/lookup [public]"
        )
