"""
net_client.py -- connects the pygame client to cloud/server.py.

pygame's main loop is synchronous (one frame at a time); the websockets
library is async. Rather than tangle the whole game in asyncio, this
runs one background thread that owns a small asyncio event loop and the
live connection. The game loop and that thread only ever talk through
two thread-safe queues:

  net.send(msg_dict)   -- game loop -> background thread -> server
  net.poll()            -- server -> background thread -> game loop
                            (call this once per frame; never blocks)

Nothing here touches pygame, and nothing in main.py touches asyncio.
"""

import asyncio
import json
import queue
import threading

import websockets


class NetClient:
    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self.incoming = queue.Queue()
        self.outgoing = queue.Queue()
        self.connected = False
        self.connect_error = None

    def connect(self, uri):
        """Start connecting in the background. Non-blocking; watch
        .connected / .connect_error to see how it went."""
        if self._thread and self._thread.is_alive():
            self.disconnect()
            self._thread.join(timeout=2)

        self._stop = threading.Event()
        self.connected = False
        self.connect_error = None

        # Clear remaining messages from previous sessions
        while not self.incoming.empty():
            try:
                self.incoming.get_nowait()
            except queue.Empty:
                break
        while not self.outgoing.empty():
            try:
                self.outgoing.get_nowait()
            except queue.Empty:
                break

        self._thread = threading.Thread(target=self._run, args=(uri,), daemon=True)
        self._thread.start()

    def disconnect(self):
        self._stop.set()
        self.outgoing.put(None)  # wakes the sender loop so it can exit

    def send(self, msg):
        self.outgoing.put(msg)

    def poll(self):
        """Return (and clear) every message received since the last poll.
        Never blocks -- safe to call every frame."""
        out = []
        while True:
            try:
                out.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return out

    # -- background thread --------------------------------------------
    def _run(self, uri):
        try:
            asyncio.run(self._main(uri))
        except Exception as e:
            self.connect_error = str(e)
        finally:
            self.connected = False

    async def _main(self, uri):
        async with websockets.connect(uri, open_timeout=5) as ws:
            self.connected = True
            
            sender = asyncio.create_task(self._pump_out(ws))
            receiver = asyncio.create_task(self._pump_in(ws))
            stopper = asyncio.create_task(self._wait_stop())

            tasks = [sender, receiver, stopper]
            try:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
                # Await pending tasks to let cancellation propagate cleanly
                await asyncio.gather(*pending, return_exceptions=True)

                for t in done:
                    if t is not stopper and t.exception():
                        self.connect_error = str(t.exception())
            finally:
                self.connected = False

    async def _pump_out(self, ws):
        while not self._stop.is_set():
            try:
                msg = self.outgoing.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue

            if msg is None or self._stop.is_set():
                return
            
            await ws.send(json.dumps(msg))

    async def _pump_in(self, ws):
        async for raw in ws:
            if self._stop.is_set():
                break
            try:
                self.incoming.put(json.loads(raw))
            except json.JSONDecodeError:
                pass

    async def _wait_stop(self):
        while not self._stop.is_set():
            await asyncio.sleep(0.05)
