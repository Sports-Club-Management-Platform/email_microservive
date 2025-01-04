from contextlib import asynccontextmanager
import asyncio
import requests
import aio_pika
import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette import status
from dotenv import load_dotenv
from barcode import EAN13
from barcode.writer import ImageWriter
import base64
from io import BytesIO

load_dotenv()

RABBITMQ_URL = os.environ.get("RABBITMQ_URL")
SERVICE_ID = os.environ.get("SERVICE_ID")
TEMPLATE_ID = os.environ.get("TEMPLATE_ID")
PUBLIC_KEY = os.environ.get("PUBLIC_KEY")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        "exchange", type=aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue("EMAILS", durable=True)
    await queue.bind(exchange, routing_key="EMAILS")

    async def rabbitmq_listener():
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    send_email(json.loads(message.body))

    # Run RabbitMQ listener in the background
    asyncio.create_task(rabbitmq_listener())
    yield
    # Cleanup
    await channel.close()
    await connection.close()
    # task.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="ClubSync Email_Microservice",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "ClubSync",
    },
    servers=[{"url": "http://localhost:8000", "description": "Local server"}],
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["healthcheck"],
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
)
def get_health():
    return {"status": "ok"}


def send_email(data):
    barcode_buffer = BytesIO()
    barcode = EAN13(data["ticket_id"], writer=ImageWriter())
    barcode.write(barcode_buffer)
    barcode_base64 = base64.b64encode(barcode_buffer.getvalue()).decode("utf-8")
    barcode_src = f"data:image/png;base64,{barcode_base64}"

    email_data = {
        "user_name": data["user_name"],
        "ticket_name": data["ticket_name"],
        "ticket_price": data["ticket_price"],
        "ticket_id": data["ticket_id"],
        "attachment": barcode_src,
        "to_email": data["to_email"],
    }

    payload = {
        "service_id": SERVICE_ID,
        "template_id": TEMPLATE_ID,
        "user_id": PUBLIC_KEY,
        "accessToken": PRIVATE_KEY,
        "template_params": email_data,
    }

    response = requests.post(
        "https://api.emailjs.com/api/v1.0/email/send",
        json=payload,  # Remove o uso de json.dumps aqui
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        print("E-mail enviado com sucesso!")
    else:
        print(f"Falha ao enviar e-mail: {response.status_code} - {response.text}")
