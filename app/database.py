from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import os, json
import httpx
import aio_pika

app = FastAPI(title="Returns Service (no DB)")

ORDERS_BASE_URL = os.getenv("ORDERS_BASE_URL", "http://localhost:8003")  # local dev default
RABBIT_URL = os.getenv("RABBIT_URL")
EXCHANGE_NAME = "events_topic"

returns_store = []
next_id = 1

class ReturnCreate(BaseModel):
    order_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=2, max_length=200)

class ReturnOut(BaseModel):
    id: int
    order_id: int
    reason: str
    status: str

class ReturnUpdate(BaseModel):
    status: str = Field(..., pattern="^(created|approved|rejected|refunded)$")

async def ensure_order_exists(order_id: int) -> dict:
    """
    Synchronously verify order exists by calling Orders service.
    Uses AsyncClient so it doesn't block the event loop.
    """
    url = f"{ORDERS_BASE_URL}/api/orders/{order_id}"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Orders service unavailable")

    if r.status_code == 404:
        raise HTTPException(status_code=400, detail="Order does not exist")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Orders service error ({r.status_code})")

    return r.json()

async def publish_event(routing_key: str, payload: dict):
    """
    Optional RabbitMQ publish. If RABBIT_URL isn't set, it will skip.
    """
    if not RABBIT_URL:
        return

    conn = await aio_pika.connect_robust(RABBIT_URL)
    ch = await conn.channel()
    ex = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC)

    msg = aio_pika.Message(body=json.dumps(payload).encode())
    await ex.publish(msg, routing_key=routing_key)

    await conn.close()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/returns", response_model=ReturnOut, status_code=status.HTTP_201_CREATED)
async def create_return(payload: ReturnCreate):
    global next_id
    order = await ensure_order_exists(payload.order_id)

    ret = {
        "id": next_id,
        "order_id": payload.order_id,
        "reason": payload.reason,
        "status": "created",
    }
    next_id += 1
    returns_store.append(ret)

    await publish_event(
        "return.created",
        {
            "return_id": ret["id"],
            "order_id": ret["order_id"],
            "reason": ret["reason"],
            "status": ret["status"],
            # keep it small—no huge nested order payload needed
            "order_status": order.get("status"),
            "total_price": order.get("total_price"),
        },
    )

    return ret

@app.get("/api/returns", response_model=list[ReturnOut])
def list_returns():
    return returns_store

@app.get("/api/returns/{return_id}", response_model=ReturnOut)
def get_return(return_id: int):
    for r in returns_store:
        if r["id"] == return_id:
            return r
    raise HTTPException(status_code=404, detail="Return not found")

@app.put("/api/returns/{return_id}", response_model=ReturnOut)
async def update_return(return_id: int, payload: ReturnUpdate):
    for r in returns_store:
        if r["id"] == return_id:
            r["status"] = payload.status

            await publish_event(
                f"return.{payload.status}",
                {"return_id": r["id"], "order_id": r["order_id"], "status": r["status"]},
            )
            return r
    raise HTTPException(status_code=404, detail="Return not found")

@app.delete("/api/returns/{return_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_return(return_id: int):
    for i, r in enumerate(returns_store):
        if r["id"] == return_id:
            returns_store.pop(i)
            return
    raise HTTPException(status_code=404, detail="Return not found")
