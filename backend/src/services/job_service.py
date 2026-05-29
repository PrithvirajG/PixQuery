from src.services.document_serializer import serialize_document, serialize_documents


class JobService:
    def __init__(self, repository, publisher_factory):
        self.repository = repository
        self.publisher_factory = publisher_factory

    def list_jobs(self, *, status: str | None = None, limit: int = 100):
        return serialize_documents(self.repository.list_jobs(status=status, limit=limit))

    async def requeue_job(self, job_id: str):
        job = self.repository.requeue_job(job_id)
        if not job:
            return None

        publisher = self.publisher_factory()
        await publisher.connect()
        try:
            await publisher.publish(job_id)
        finally:
            await publisher.close()
        return serialize_document(job)

