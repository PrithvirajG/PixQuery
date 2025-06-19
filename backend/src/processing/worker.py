from rq import Worker, Queue
from redis import Redis

def start_worker(queue_name='photos'):
    redis_conn = Redis(host="localhost", port=6379)
    queue = Queue(name=queue_name, connection=redis_conn)
    worker = Worker(queues=[queue], connection=redis_conn)
    worker.work()

if __name__ == '__main__':
    start_worker()
