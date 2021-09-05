#!/usr/bin/env python

# server.py - simple 'microservice' serving results of the fibonacci sequence
from socket import *
from select import select
from collections import deque

from fib import fib


# This is a version of the server that uses raw generators to implement a task scheduler.
# Compared to the server_generators.py it wraps the sockets and client to "hide" the
# details of the scheduler


tasks = deque()     # queue of tasks
recv_wait = {}      # tasks awaiting a receive operation
send_wait = {}      # tasks awaiting a send operation


def run():
    while any([tasks, recv_wait, send_wait]):
        while not tasks:
            # no active tasks to run - wait for I/O
            # Polls the operating system about which handles (sockets, clients),
            # are ready to return some data (i.e. essentially with no blocking).
            can_recv, can_send, _ = select(recv_wait, send_wait, [])
            tasks.extend(recv_wait.pop(t) for t in can_recv)
            tasks.extend(send_wait.pop(t) for t in can_send)

        # Otherwise - round-robin schedule the active tasks
        task = tasks.popleft()
        try:
            # Run to the next yield.
            # Yield will return the information `why` the task is suspended,
            # and `what` - the object that it will be suspended on.
            why, what = next(task)
            if why == 'recv':
                # Must go wait somewhere
                recv_wait[what] = task
            elif why == 'send':
                send_wait[what] = task
            else:
                raise RuntimeError('Invalid operation')
        except StopIteration:
            print("Task done")


# This class hides the details necessary to make the task scheduler work.
# The yielded values, handled by the scheduler are no longer visible in
# the business-logic part of code. They can now be hidden behind a 'yield from'.
class AsyncSocket:
    def __init__(self, sock):
        self.sock = sock

    def recv(self, maxsize):
        yield 'recv', self.sock
        return self.sock.recv(maxsize)

    def send(self, data):
        yield 'send', self.sock
        return self.sock.send(data)

    def accept(self):
        yield 'recv', self.sock
        client, addr = self.sock.accept()
        return AsyncSocket(client), addr

    def __getattr__(self, name):
        return getattr(self.sock, name)


def fib_server(address):
    sock = AsyncSocket(socket(AF_INET, SOCK_STREAM))
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sock.bind(address)
    sock.listen(5)
    while True:
        # yield 'recv', sock
        client, addr = yield from sock.accept()
        print("Connection", addr)
        tasks.append(fib_handler(client))


def fib_handler(client):
    while True:
        # yield 'recv', client
        req = yield from client.recv(100)
        if not req:
            break
        try:
            n = int(req)
            result = fib(n)
        except ValueError:
            result = 'Error: Invalid input'
        resp = str(result).encode('ascii') + b'\n'
        # yield 'send', client
        yield from client.send(resp) 
    print("Closed.")


if __name__ == '__main__':
    try:
        tasks.append(fib_server(('', 25000)))
        run()
    except KeyboardInterrupt:
        print("Server shutting down...")
