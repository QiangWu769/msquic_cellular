//
// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
//

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <msquic.h>
#include <quic_platform.h>

//
// The default port used for connecting to the server.
//
#define DEFAULT_QUIC_PORT 4433

//
// The default server name used for SNI and certificate validation.
//
#define DEFAULT_SERVER_NAME "localhost"

//
// The default IP address to connect to.
//
#define DEFAULT_SERVER_IP "127.0.0.1"

//
// The default upload size (10 MB).
//
#define DEFAULT_UPLOAD_LENGTH (10 * 1024 * 1024)

//
// The default upload buffer size.
//
#define DEFAULT_UPLOAD_BUFFER_SIZE (64 * 1024)

//
// Represents a single connection to the server.
//
typedef struct QUIC_CLIENT_CONNECTION {
    HQUIC Connection;
    HQUIC Stream;
    uint64_t UploadLength;
    uint64_t UploadedBytes;
    uint8_t* SendBuffer;
    uint32_t SendBufferLength;
    QUIC_BUFFER SendQuicBuffer;
    QUIC_EVENT UploadComplete;
    BOOLEAN Connected;
} QUIC_CLIENT_CONNECTION;

//
// The global configuration.
//
HQUIC Configuration;
const QUIC_API_TABLE* MsQuic;
HQUIC Registration;
QUIC_CLIENT_CONNECTION ClientConnection;

//
// Handler for stream events from MsQuic.
//
_IRQL_requires_max_(DISPATCH_LEVEL)
_Function_class_(QUIC_STREAM_CALLBACK)
QUIC_STATUS
QUIC_API
ClientStreamCallback(
    _In_ HQUIC Stream,
    _In_opt_ void* Context,
    _Inout_ QUIC_STREAM_EVENT* Event
    )
{
    QUIC_CLIENT_CONNECTION* Client = (QUIC_CLIENT_CONNECTION*)Context;

    switch (Event->Type) {
    case QUIC_STREAM_EVENT_SEND_COMPLETE:
        if (Event->SEND_COMPLETE.Canceled) {
            printf("[stream][%p] Send canceled!\n", Stream);
            break;
        }
        
        Client->UploadedBytes += Event->SEND_COMPLETE.Length;
        
        if (Client->UploadedBytes >= Client->UploadLength) {
            // Upload complete, shutdown the stream
            printf("[stream][%p] Upload complete! (%llu bytes)\n", 
                Stream, (unsigned long long)Client->UploadedBytes);
            MsQuic->StreamShutdown(
                Stream,
                QUIC_STREAM_SHUTDOWN_FLAG_GRACEFUL,
                0);
        } else {
            // Continue uploading
            uint64_t BytesRemaining = Client->UploadLength - Client->UploadedBytes;
            uint32_t BytesToSend = 
                (uint32_t)CXPLAT_MIN(BytesRemaining, Client->SendBufferLength);
            
            Client->SendQuicBuffer.Length = BytesToSend;
            
            QUIC_STATUS Status =
                MsQuic->StreamSend(
                    Stream,
                    &Client->SendQuicBuffer,
                    1,
                    QUIC_SEND_FLAG_NONE,
                    &Client->SendQuicBuffer);
                    
            if (QUIC_FAILED(Status)) {
                printf("[stream][%p] StreamSend failed, 0x%x!\n", Stream, Status);
            }
        }
        break;

    case QUIC_STREAM_EVENT_PEER_SEND_SHUTDOWN:
        printf("[stream][%p] Peer shutdown\n", Stream);
        break;

    case QUIC_STREAM_EVENT_PEER_SEND_ABORTED:
        printf("[stream][%p] Peer aborted\n", Stream);
        break;

    case QUIC_STREAM_EVENT_SHUTDOWN_COMPLETE:
        printf("[stream][%p] Shutdown complete\n", Stream);
        MsQuic->StreamClose(Stream);
        CxPlatEventSet(Client->UploadComplete);
        break;

    default:
        break;
    }

    return QUIC_STATUS_SUCCESS;
}

//
// Handler for connection events from MsQuic.
//
_IRQL_requires_max_(DISPATCH_LEVEL)
_Function_class_(QUIC_CONNECTION_CALLBACK)
QUIC_STATUS
QUIC_API
ClientConnectionCallback(
    _In_ HQUIC Connection,
    _In_opt_ void* Context,
    _Inout_ QUIC_CONNECTION_EVENT* Event
    )
{
    QUIC_CLIENT_CONNECTION* Client = (QUIC_CLIENT_CONNECTION*)Context;

    switch (Event->Type) {
    case QUIC_CONNECTION_EVENT_CONNECTED:
        printf("[conn][%p] Connected\n", Connection);
        Client->Connected = TRUE;
        
        // Create a stream for uploading data
        QUIC_STATUS Status =
            MsQuic->StreamOpen(
                Connection,
                QUIC_STREAM_OPEN_FLAG_UNIDIRECTIONAL,
                ClientStreamCallback,
                Client,
                &Client->Stream);
                
        if (QUIC_FAILED(Status)) {
            printf("[conn][%p] StreamOpen failed, 0x%x!\n", Connection, Status);
            break;
        }
        
        Status = MsQuic->StreamStart(Client->Stream, QUIC_STREAM_START_FLAG_NONE);
        if (QUIC_FAILED(Status)) {
            printf("[conn][%p] StreamStart failed, 0x%x!\n", Connection, Status);
            MsQuic->StreamClose(Client->Stream);
            Client->Stream = NULL;
            break;
        }
        
        // Start uploading data
        Client->SendQuicBuffer.Buffer = Client->SendBuffer;
        Client->SendQuicBuffer.Length = 
            (uint32_t)CXPLAT_MIN(Client->UploadLength, Client->SendBufferLength);
            
        Status =
            MsQuic->StreamSend(
                Client->Stream,
                &Client->SendQuicBuffer,
                1,
                QUIC_SEND_FLAG_NONE,
                &Client->SendQuicBuffer);
                
        if (QUIC_FAILED(Status)) {
            printf("[conn][%p] StreamSend failed, 0x%x!\n", Connection, Status);
            MsQuic->StreamClose(Client->Stream);
            Client->Stream = NULL;
        }
        break;

    case QUIC_CONNECTION_EVENT_SHUTDOWN_INITIATED_BY_TRANSPORT:
        printf("[conn][%p] Shutdown by transport, 0x%x\n", Connection, Event->SHUTDOWN_INITIATED_BY_TRANSPORT.Status);
        break;

    case QUIC_CONNECTION_EVENT_SHUTDOWN_INITIATED_BY_PEER:
        printf("[conn][%p] Shutdown by peer, 0x%lx\n", Connection, Event->SHUTDOWN_INITIATED_BY_PEER.ErrorCode);
        break;

    case QUIC_CONNECTION_EVENT_SHUTDOWN_COMPLETE:
        printf("[conn][%p] Shutdown complete\n", Connection);
        if (!Client->Connected) {
            printf("[conn][%p] Failed to connect!\n", Connection);
            CxPlatEventSet(Client->UploadComplete);
        }
        break;

    default:
        break;
    }

    return QUIC_STATUS_SUCCESS;
}

//
// Initializes the client connection.
//
BOOLEAN
ClientInitialize(
    _In_ int argc,
    _In_reads_(argc) _Null_terminated_ char* argv[]
    )
{
    QUIC_STATUS Status;
    BOOLEAN Ret = FALSE;
    QUIC_SETTINGS Settings = {0};
    QUIC_CREDENTIAL_CONFIG CredConfig;
    
    // Initialize client connection context
    CxPlatZeroMemory(&ClientConnection, sizeof(ClientConnection));
    ClientConnection.UploadLength = DEFAULT_UPLOAD_LENGTH;
    ClientConnection.SendBufferLength = DEFAULT_UPLOAD_BUFFER_SIZE;
    
    // Parse command line arguments
    const char* ServerName = DEFAULT_SERVER_NAME;
    const char* ServerIp = DEFAULT_SERVER_IP;
    uint16_t ServerPort = DEFAULT_QUIC_PORT;
    
    for (int i = 0; i < argc; i++) {
        if (strcmp(argv[i], "-server") == 0 && i + 1 < argc) {
            ServerName = argv[i + 1];
            i++;
        } else if (strcmp(argv[i], "-ip") == 0 && i + 1 < argc) {
            ServerIp = argv[i + 1];
            i++;
        } else if (strcmp(argv[i], "-port") == 0 && i + 1 < argc) {
            ServerPort = (uint16_t)atoi(argv[i + 1]);
            i++;
        } else if (strcmp(argv[i], "-upload") == 0 && i + 1 < argc) {
            ClientConnection.UploadLength = (uint64_t)atoll(argv[i + 1]);
            i++;
        }
    }
    
    // Allocate send buffer
    ClientConnection.SendBuffer = malloc(ClientConnection.SendBufferLength);
    if (ClientConnection.SendBuffer == NULL) {
        printf("Failed to allocate send buffer!\n");
        goto Error;
    }
    
    // Fill buffer with pattern
    for (uint32_t i = 0; i < ClientConnection.SendBufferLength; ++i) {
        ClientConnection.SendBuffer[i] = (uint8_t)(i % 256);
    }
    
    // Create upload complete event
    if (QUIC_FAILED(CxPlatEventInitialize(&ClientConnection.UploadComplete, FALSE, FALSE))) {
        printf("CxPlatEventInitialize failed!\n");
        goto Error;
    }
    
    // Open registration with MsQuic
    if (QUIC_FAILED(
            Status = MsQuic->RegistrationOpen(
                NULL, &Registration))) {
        printf("RegistrationOpen failed, 0x%x!\n", Status);
        goto Error;
    }
    
    // Configure QUIC settings
    Settings.IsSet.CongestionControlAlgorithm = TRUE;
    Settings.CongestionControlAlgorithm = QUIC_CONGESTION_CONTROL_ALGORITHM_BBR;
    Settings.IsSet.IdleTimeoutMs = TRUE;
    Settings.IdleTimeoutMs = 30000;
    Settings.IsSet.SendBufferingEnabled = TRUE;
    Settings.SendBufferingEnabled = TRUE;
    Settings.IsSet.PacingEnabled = TRUE;
    Settings.PacingEnabled = TRUE;
    
    // Create configuration
    if (QUIC_FAILED(
            Status = MsQuic->ConfigurationOpen(
                Registration,
                NULL,
                0,
                &Settings,
                sizeof(Settings),
                NULL,
                &Configuration))) {
        printf("ConfigurationOpen failed, 0x%x!\n", Status);
        goto Error;
    }
    
    // Load credentials
    CxPlatZeroMemory(&CredConfig, sizeof(CredConfig));
    CredConfig.Type = QUIC_CREDENTIAL_TYPE_NONE;
    CredConfig.Flags = QUIC_CREDENTIAL_FLAG_CLIENT | QUIC_CREDENTIAL_FLAG_NO_CERTIFICATE_VALIDATION;
    
    if (QUIC_FAILED(
            Status = MsQuic->ConfigurationLoadCredential(
                Configuration,
                &CredConfig))) {
        printf("ConfigurationLoadCredential failed, 0x%x!\n", Status);
        goto Error;
    }
    
    // Create connection
    if (QUIC_FAILED(
            Status = MsQuic->ConnectionOpen(
                Registration,
                ClientConnectionCallback,
                &ClientConnection,
                &ClientConnection.Connection))) {
        printf("ConnectionOpen failed, 0x%x!\n", Status);
        goto Error;
    }
    
    // Set server name
    if (QUIC_FAILED(
            Status = MsQuic->SetParam(
                ClientConnection.Connection,
                QUIC_PARAM_CONN_REMOTE_ADDRESS,
                sizeof(QUIC_ADDR),
                &ServerIp))) {
        printf("SetParam QUIC_PARAM_CONN_REMOTE_ADDRESS failed, 0x%x!\n", Status);
        goto Error;
    }
    
    // Start connection
    if (QUIC_FAILED(
            Status = MsQuic->ConnectionStart(
                ClientConnection.Connection,
                QUIC_ADDRESS_FAMILY_UNSPEC,
                ServerName,
                ServerPort))) {
        printf("ConnectionStart failed, 0x%x!\n", Status);
        goto Error;
    }
    
    printf("Connecting to %s:%hu for uploading %llu bytes...\n", 
        ServerName, ServerPort, (unsigned long long)ClientConnection.UploadLength);
    
    Ret = TRUE;
    
Error:
    if (!Ret) {
        if (ClientConnection.Connection != NULL) {
            MsQuic->ConnectionClose(ClientConnection.Connection);
            ClientConnection.Connection = NULL;
        }
        if (Configuration != NULL) {
            MsQuic->ConfigurationClose(Configuration);
            Configuration = NULL;
        }
        if (Registration != NULL) {
            MsQuic->RegistrationClose(Registration);
            Registration = NULL;
        }
        if (ClientConnection.SendBuffer != NULL) {
            free(ClientConnection.SendBuffer);
            ClientConnection.SendBuffer = NULL;
        }
    }
    
    return Ret;
}

//
// Cleans up the client connection.
//
void
ClientCleanup(
    )
{
    if (ClientConnection.Stream != NULL) {
        MsQuic->StreamClose(ClientConnection.Stream);
    }
    if (ClientConnection.Connection != NULL) {
        MsQuic->ConnectionClose(ClientConnection.Connection);
    }
    if (Configuration != NULL) {
        MsQuic->ConfigurationClose(Configuration);
    }
    if (Registration != NULL) {
        MsQuic->RegistrationClose(Registration);
    }
    if (ClientConnection.SendBuffer != NULL) {
        free(ClientConnection.SendBuffer);
    }
    CxPlatEventUninitialize(ClientConnection.UploadComplete);
}

//
// The main entry point to the app.
//
int
QUIC_MAIN_EXPORT
main(
    _In_ int argc,
    _In_reads_(argc) _Null_terminated_ char* argv[]
    )
{
    QUIC_STATUS Status = QUIC_STATUS_SUCCESS;
    
    // Initialize MsQuic
    if (QUIC_FAILED(Status = MsQuicOpen(&MsQuic))) {
        printf("MsQuicOpen failed, 0x%x!\n", Status);
        return Status;
    }
    
    // Initialize client
    if (ClientInitialize(argc, argv)) {
        // Wait for the upload to complete
        CxPlatEventWaitForever(ClientConnection.UploadComplete);
    }
    
    // Cleanup
    ClientCleanup();
    MsQuicClose(MsQuic);
    
    return 0;
} 