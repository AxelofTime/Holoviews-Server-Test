from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
import zmq
from functools import partial

def make_document(context, doc):
    print("Make doc")
    port = 5006
    socket = context.socket(zmq.SUB)
    # MUST BE FROM SAME MACHINE, CHANGE IF NECESSARY!!!
    socket.connect("tcp://psanagpu114:%d" % port)
    socket.setsockopt(zmq.SUBSCRIBE, b"")
    
    def update():
        print("Update")
        if socket.poll(timeout=0):
            stuff = socket.recv_pyobj()
            print(stuff.keys())

    doc.add_periodic_callback(update, 1000)

context = zmq.Context()

apps = {'/': Application(FunctionHandler(partial(make_document, context)))}
server = Server(apps, port=5000)

server.start()
server.io_loop.add_callback(server.show, '/')

server.io_loop.start()