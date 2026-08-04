import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as c:
        r = await c.get('https://gstaccelerator.in/api/v1/hsn/08109030', headers={'x-api-key':'test'})
        print('GET:', r.status_code, r.text)
        r2 = await c.post('https://gstaccelerator.in/api/v1/lookup', json={'description': 'sapota'}, headers={'x-api-key':'test'})
        print('POST:', r2.status_code, r2.text)

asyncio.run(main())
