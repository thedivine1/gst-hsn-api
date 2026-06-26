from locust import HttpUser, task, between

class APIUser(HttpUser):
    # Simulate a user waiting 1 to 3 seconds between actions
    wait_time = between(1, 3)

    # Use the demo API key
    headers = {"X-API-Key": "gsta_demo_frontend", "Content-Type": "application/json"}

    @task(3)
    def test_lookup(self):
        """Simulate a user searching by description (happens 3x more often than direct code lookup)"""
        self.client.post("/v1/lookup", json={"description": "rice"}, headers=self.headers)
        
    @task(1)
    def test_lookup_complex(self):
        """Simulate a user searching with advanced condition flags"""
        payload = {
            "description": "cotton shirt",
            "branded": True,
            "sale_value_inr": 1500,
            "b2b": False
        }
        self.client.post("/v1/lookup", json=payload, headers=self.headers)

    @task(2)
    def test_hsn_exact(self):
        """Simulate a user doing a direct HSN lookup"""
        self.client.get("/v1/hsn/84151010", headers=self.headers)

    @task(1)
    def test_summary(self):
        """Simulate a dashboard hit to the summary endpoint"""
        self.client.get("/v1/rates/summary", headers=self.headers)
