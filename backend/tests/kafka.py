import asyncio
from contextlib import suppress

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError
from testcontainers.community.kafka import KafkaContainer


class KafkaServer:
    """Kafka в контейнере (режим KRaft, без ZooKeeper)."""

    IMAGE = "confluentinc/cp-kafka:7.6.1"

    def __init__(self) -> None:
        self._container = KafkaContainer(self.IMAGE).with_kraft()

    def start(self) -> None:
        self._container.start()

    def stop(self) -> None:
        self._container.stop()

    @property
    def bootstrap_servers(self) -> str:
        return str(self._container.get_bootstrap_server())

    async def create_topics(self, *names: str) -> None:
        admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        await admin.start()

        try:
            with suppress(TopicAlreadyExistsError):
                await admin.create_topics(
                    [NewTopic(name, num_partitions=1, replication_factor=1) for name in names]
                )
        finally:
            await admin.close()

        await asyncio.sleep(0.5)
