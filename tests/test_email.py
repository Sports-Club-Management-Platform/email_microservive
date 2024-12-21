import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import aio_pika
from main import send_email, lifespan


@patch("requests.post")  # Mock da função requests.post
def test_send_email_success(mock_post):
    # Configurando a resposta simulada
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "Success"

    # Dados de exemplo
    data = {
        "user_name": "André Oliveira",
        "ticket_name": "Finais",
        "ticket_price": "150",
        "ticket_id": "78910",
        "to_email": "andreoliveira.net1@gmail.com",
    }

    # Executando a função
    send_email(data)

    # Verificando se requests.post foi chamado com os parâmetros corretos
    assert mock_post.call_count == 1
    assert "Success" in mock_post.return_value.text
    assert mock_post.call_args[1]["json"] == {
        "service_id": os.environ.get("SERVICE_ID"),
        "template_id": os.environ.get("TEMPLATE_ID"),
        "user_id": os.environ.get("PUBLIC_KEY"),
        "accessToken": os.environ.get("PRIVATE_KEY"),
        "template_params": data,
    }
    assert mock_post.return_value.status_code == 200


@patch("requests.post")  # Mock da função requests.post
def test_send_email_failure(mock_post):
    # Configurando a resposta simulada
    mock_post.return_value.status_code = 400
    mock_post.return_value.text = "Bad Request"

    # Dados de exemplo
    data = {
        "user_name": "André Oliveira",
        "ticket_name": "Finais",
        "ticket_price": "150",
        "ticket_id": "78910",
        "to_email": "andreoliveira.net1@gmail.com",
    }

    # Executando a função
    send_email(data)

    # Verificando se requests.post foi chamado com os parâmetros corretos
    assert mock_post.call_count == 1
    assert "Bad Request" in mock_post.return_value.text


@pytest.mark.asyncio
@patch("aio_pika.connect_robust")  # Mock da conexão com RabbitMQ
async def test_lifespan(mock_connect_robust):
    # Configurando mocks para a conexão RabbitMQ
    mock_connection = AsyncMock()  # Use AsyncMock para objetos que serão "awaited"
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()
    mock_exchange = AsyncMock()

    mock_connect_robust.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_exchange.return_value = mock_exchange
    mock_channel.declare_queue.return_value = mock_queue

    app = MagicMock()

    async with lifespan(app):
        # Verifique se a conexão, canal e fila foram chamados
        mock_connect_robust.assert_called_once_with(os.environ.get("RABBITMQ_URL"))
        mock_channel.declare_exchange.assert_called_once_with(
            "exchange", type=aio_pika.ExchangeType.TOPIC, durable=True
        )
        mock_channel.declare_queue.assert_called_once_with("EMAILS", durable=True)
