# End to end Example of a NuroPb setup with a GW

This example shows how to configure a NuroPb service with a GW that exposes a WebSocket
endpoint that enables service calls to the service mesh over the WebSocket connection. 

## Prerequisites

1. An instance of RabbitMQ
2. Install the python modules nuropb and nuropb_gw (this package)

## Running the example
1. Run gw_init_mesh.py to initialize the RabbitMQ nuropb service mesh
2. Run gw_ws_server.py to start an example Mesh Service
3. Run gw_ws_server.py to start an example Mesh Gateway
4. Run gw_ws_client_swarm.py simulate clients using to the Mesh Gateway 




