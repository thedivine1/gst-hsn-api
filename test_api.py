import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get('http://localhost:8000/api/v1/hsn/08109030', headers={'x-api-key':'test'})
        print("GET", r.status_code, r.text)
        r2 = await client.post('http://localhost:8000/api/v1/lookup', json={'description': 'sapota'}, headers={'x-api-key':'test'})
        print("POST", r2.status_code, [m["hsn_code"] for m in r2.json()])

asyncio.run(main())
