from settings import settings

from .rabbitmq_manager import RabbitMQ

amqp_connection_string = (
    'amqp://{user}:{password}@{host}:{port}/'.format(
        user=settings.amqp_user,
        password=settings.amqp_password,
        host=settings.amqp_host,
        port=settings.amqp_port
    )
)

rabbit_mq = RabbitMQ(amqp_connection_string, settings.core_channel_number)
