from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

import os, json
import aio_pika

from .database import get_db, engine
from .models import Base, Return
from .schemas import ReturnCreate, ReturnUpdate, ReturnOut

app = FastAPI(title="Returns Service")
Base.metadata.create_all(bind=engine)


RABBIT_URL = os.getenv("RABBIT_URL")
EXCHANGE_NAME = "events_topic"

async def publish_event(routing_key: str, payload: dict):
    if not RABBIT_URL:
        print("RABBIT_URL not set — skipping publish")
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
async def create_return(payload: ReturnCreate, db: Session = Depends(get_db)):
    ret = Return(order_id=payload.order_id, reason=payload.reason, status="created")
    db.add(ret)
    db.commit()
    db.refresh(ret)
    
    await publish_event(
        "return.created",
        {"return_id": ret.id, "order_id": ret.order_id, "reason": ret.reason, "status": ret.status}
    )

    return ret

@app.get("/api/returns", response_model=list[ReturnOut])
def list_returns(db: Session = Depends(get_db)):
    return db.execute(select(Return)).scalars().all()

@app.get("/api/returns/{return_id}", response_model=ReturnOut)
def get_return(return_id: int, db: Session = Depends(get_db)):
    ret = db.execute(select(Return).where(Return.id == return_id)).scalar_one_or_none()
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    return ret

@app.put("/api/returns/{return_id}", response_model=ReturnOut)
async def update_return(return_id: int, payload: ReturnUpdate, db: Session = Depends(get_db)):
    ret = db.execute(select(Return).where(Return.id == return_id)).scalar_one_or_none()
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    ret.status = payload.status
    db.commit()
    db.refresh(ret)
    
    await publish_event(
        f"return.{ret.status}",
        {"return_id": ret.id, "order_id": ret.order_id, "status": ret.status}
    )

    return ret

@app.delete("/api/returns/{return_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_return(return_id: int, db: Session = Depends(get_db)):
    ret = db.execute(select(Return).where(Return.id == return_id)).scalar_one_or_none()
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    db.delete(ret)
    db.commit()
    return
