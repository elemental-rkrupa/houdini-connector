#include <HAPI/HAPI.h>
#include <iostream>
#include <string>

#define ENSURE_SUCCESS( result ) \
if ( (result) != HAPI_RESULT_SUCCESS ) \
{ \
    std::cout << "Failure at " << __FILE__ << ": " << __LINE__ << std::endl; \
    std::cout << getLastError() << std::endl; \
    cleanupAndExit( &session, 1 ); \
}

#define ENSURE_COOK_SUCCESS( result ) \
if ( (result) != HAPI_RESULT_SUCCESS ) \
{ \
    std::cout << "Failure at " << __FILE__ << ": " << __LINE__ << std::endl; \
    std::cout << getLastCookError() << std::endl; \
    cleanupAndExit( &session, 1 ); \
}

#define REPORT_SUCCESS( result ) \
if ( (result) != HAPI_RESULT_SUCCESS ) \
{ \
    std::cout << "Failure at " << __FILE__ << ": " << __LINE__ << std::endl; \
    std::cout << getLastError() << std::endl; \
}

#define REPORT_COOK_SUCCESS( result ) \
if ( (result) != HAPI_RESULT_SUCCESS ) \
{ \
    std::cout << "Failure at " << __FILE__ << ": " << __LINE__ << std::endl; \
    std::cout << getLastCookError() << std::endl; \
}

static std::string getLastError();
static std::string getLastCookError();
static std::string getString( HAPI_StringHandle stringHandle );
static void cleanupAndExit(HAPI_Session *inSession, int code);

int
main( int argc, char ** argv )
{
    // NB: The TEST_DATA_DIR environment variable must be set
    // in order to open the default hda.
    const char * hdaFile = argc == 2 ? argv[ 1 ] : "$TEST_DATA_DIR/omni_test_export_usd.hda";
    
    HAPI_CookOptions cookOptions = HAPI_CookOptions_Create();

    HAPI_Session session;

    HAPI_CreateInProcessSession( &session );

    ENSURE_SUCCESS( HAPI_Initialize( &session,
				     &cookOptions,
				     true,
				     -1,
				     nullptr,
				     nullptr,
				     nullptr,
				     nullptr,
				     nullptr ) );

    HAPI_AssetLibraryId assetLibId;
    ENSURE_SUCCESS( HAPI_LoadAssetLibraryFromFile( &session, hdaFile, true, &assetLibId ) );

    int assetCount;
    ENSURE_SUCCESS( HAPI_GetAvailableAssetCount( &session, assetLibId, &assetCount ) );

    if (assetCount > 1)
    {
	    std::cout << "Should only be loading 1 asset here" << std::endl;
	    cleanupAndExit ( &session, 1 );
    }
    
    HAPI_StringHandle assetSh;
    ENSURE_SUCCESS( HAPI_GetAvailableAssets( &session, assetLibId, &assetSh, assetCount ) );

    std::string assetName = getString( assetSh );

    HAPI_NodeId nodeId;
    ENSURE_SUCCESS( HAPI_CreateNode( &session, -1, assetName.c_str(), "TestAsset", false, &nodeId ) );

    ENSURE_SUCCESS( HAPI_CookNode( &session, nodeId, &cookOptions ) );
    
    int cookStatus;
    HAPI_Result cookResult;

    do
    {
	    cookResult = HAPI_GetStatus( &session, HAPI_STATUS_COOK_STATE, &cookStatus );
    }
    while (cookStatus > HAPI_STATE_MAX_READY_STATE && cookResult == HAPI_RESULT_SUCCESS);

    REPORT_SUCCESS(cookResult);
    REPORT_COOK_SUCCESS(cookStatus);

    // Regardless of the cook result or status, we press the execute and Validate buttons to
    // report errors.
    ENSURE_SUCCESS(HAPI_SetParmIntValue(&session, nodeId, "execute", 0, 1));

    // Regardless of the cook result or status, we press the Validate button to
    // report errors.
    ENSURE_SUCCESS(HAPI_SetParmIntValue(&session, nodeId, "validatebutton", 0, 1));

    int errCode = cookResult != HAPI_RESULT_SUCCESS || cookStatus != HAPI_RESULT_SUCCESS;

    int intVal = 0;

    HAPI_GetParmIntValue(&session, nodeId, "haserrors", 0, &intVal);

    if (intVal)
    {
        std::cout << hdaFile << " has errors." << std::endl;
        errCode = 1;
    }

    intVal = 0;

    HAPI_GetParmIntValue(&session, nodeId, "haswarnings", 0, &intVal);

    if (intVal)
    {
        std::cout << hdaFile << " has warnings." << std::endl;
        errCode = 1;
    }

    HAPI_Cleanup( &session );
    
    return errCode;
}

static void cleanupAndExit(HAPI_Session *inSession, int code)
{
    HAPI_Cleanup(inSession);
    exit(code);
}

static std::string
getLastError()
{
    int bufferLength;
    HAPI_GetStatusStringBufLength( nullptr,
				   HAPI_STATUS_CALL_RESULT,
				   HAPI_STATUSVERBOSITY_ERRORS,
				   &bufferLength );

    char * buffer = new char[ bufferLength ];

    HAPI_GetStatusString( nullptr, HAPI_STATUS_CALL_RESULT, buffer, bufferLength );

    std::string result( buffer );
    delete [] buffer;

    return result;
}

static std::string
getLastCookError()
{
    int bufferLength;
    HAPI_GetStatusStringBufLength( nullptr,
				   HAPI_STATUS_COOK_RESULT,
				   HAPI_STATUSVERBOSITY_ERRORS,
				   &bufferLength );

    char * buffer = new char[ bufferLength ];

    HAPI_GetStatusString( nullptr, HAPI_STATUS_COOK_RESULT, buffer, bufferLength );

    std::string result( buffer );
    delete[] buffer;

    return result;
}

static std::string
getString( HAPI_StringHandle stringHandle )
{
    if ( stringHandle == 0 )
    {
	return "";
    }

    int bufferLength;
    HAPI_GetStringBufLength( nullptr,
				   stringHandle,
				   &bufferLength );

    char * buffer = new char[ bufferLength ];

    HAPI_GetString ( nullptr, stringHandle, buffer, bufferLength );

    std::string result( buffer );
    delete [] buffer;

    return result;
}
