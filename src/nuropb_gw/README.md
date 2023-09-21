# TCP(WebSocket) Service Mesh Gateway

There are two primary classes that interact together in providing `consumer` access
to the services hosted on the Service Mesh. It's always tricky how to coordinate the 
dependencies between classes, especially when there are bidirectional flows and 
process between them.

Consumers are external to the service mesh, and are considered to be untrusted,
and the nature of the connections to be less reliable. The service mesh transport 
protocol is implemented AMQP over TCP and is more challenging for broad adoption,
and especially from browsers and mobile devices. The solution is to provide a 
WebSocket gateway interface to the service mesh.

The **HandlerManager** is responsible for incoming tcp (websocket) connections, and the 
**ServiceMeshManager**, which is responsible for proxying communications to the service 
mesh.

The final design is somewhat under consideration, with the options being:
* Having an overarching coordination class, i.e. a manager of managers
* or the current design where the ServiceMeshManager is both the service mesh proxy
  and the HandlerManager's manager.

It's acknowledge that the two classes are tightly coupled. The physical separation
helps with logical separation of responsibilities and the ability to test them.

It is important to **NOTE** that there's a one-to-one relationship between the
HandlerManager and ServiceMeshManager. The design requires that for each handler
type, there's a dedicated HandlerManager and by inference, a dedicated
ServiceMeshManager with its own connection to the service mesh.

### handler_manager.HandlerManager
The HandlerManager is responsible for TCP(WebSocket) connection handlers, and does 
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

### service_mesh_manager.ServiceMeshManager
* Manages a (NuroPb API) connection to the service mesh.
* Passes messages between HandlerManager and the service mesh API
* Tracks the state of asynchronous requests from handlers and directs responses
  from the service mesh back to the originating handler.
* Is responsible for its and only its, connection authorisation to the service mesh
  transport layer and broker. NOT any on-behalf-of authorisation for handler
  connections.

### Authentication and Authorization

The HandlerManager is not responsible for authentication. It is designed to verify
that authentication has already been done through validating an authorization token 
provided when a new handler is registered. A bearer token is assumed, however there
is plenty of scope for other passwordless authentication mechanisms.

## Implementation instantiation and injection:

On ServiceMeshManager instantiation, and instance of the HandlerManager is passed in.
```python
from nuropb_gw.handler_manager import HandlerManager
from nuropb_gw.service_mesh_manager import ServiceMeshManager

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
