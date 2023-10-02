# NuroPb Gateway

A library providing a WebSocket(TCP) gateway for the Nuropb service mesh. The
library leverages the [Tornado](https://tornadoweb.org) asynchronous networking 
framework, which can also be used as a template for other TCP connection handlers. 

Consumers are applications and services external to the service mesh, and 
are considered untrusted, the nature of their connections are assumed less 
reliable. 

There are two primary classes that coordinate to provide consumer access via
the gateway to services hosted on the Mesh:
* **HandlerManager** handles incoming websocket connections
* **ServiceMeshManager** which proxies flow between the handlers and the mesh.

```{note}
There's a one-to-one relationship between the HandlerManager and 
ServiceMeshManager. The design requires that for each handler type, there's a 
dedicated HandlerManager and by inference, a dedicated ServiceMeshManager 
with its own connection to the service mesh.
```

## HandlerManager
The HandlerManager is responsible for WebSocket connection handlers, and does 
the following:
* Registers handlers for incoming connections
* Unregistering handlers for closed connections
* Authorization validation of new connections
* Receiving messages from handlers
* Sending messages to handlers
* Sending messages to:
  * all registered handlers
  * one specific handler
  * all handlers registered to one user or a set of specific users

## ServiceMeshManager
* Manages a (NuroPb API) connection to the service mesh.
* Passes messages between HandlerManager and the service mesh API
* Tracks the state of asynchronous requests from handlers and directs responses
  from the service mesh back to the originating handler.
* Is responsible for its and only its, connection authorisation to the service mesh
  transport layer and broker. NOT any on-behalf-of authorisation for handler
  connections.

## Authentication and Authorization

The HandlerManager is not responsible for authentication. It is designed to verify
that authentication has already been done through validating an authorization token 
provided when a new handler is registered. A bearer token is assumed, however there
is plenty of scope for other passwordless authentication mechanisms.

## Implementation instantiation and injection:

On ServiceMeshManager instantiation, and instance of the HandlerManager is passed in.
```python
handler_manager = HandlerManager(
    ...
)
service_mesh_manager = ServiceMeshManager(
    ...,
    handler_manager=handler_manager,
)
```

The challenge provide by this assembly, if forwarding incoming messages from the handlers
to the service mesh. the HandlerManager provides a callback function to be called when
a message is received, `on_handler_message_received`.

There are not many times when HandlerManager is initialised with on_handler_message_received, 
as it is instantiated before ServiceMeshManager. It is however set by the ServiceMeshManager
during its instantiation, as follows:

```python
self._handler_manager = handler_manager
self._handler_manager._on_handler_message_received = self._on_handler_message_received
```
