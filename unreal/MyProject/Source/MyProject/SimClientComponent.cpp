#include "SimClientComponent.h"
#include "HttpModule.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "JsonUtilities.h"

USimClientComponent::USimClientComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void USimClientComponent::BeginPlay()
{
    Super::BeginPlay();
    CallLoad();
}

void USimClientComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    CallSave();
    Super::EndPlay(EndPlayReason);
}

/* ---------------- public wrappers ---------------- */

void USimClientComponent::CallLoad()
{
    SendPOST(TEXT("/load"), TEXT("{}"));
}

void USimClientComponent::CallSave()
{
    SendPOST(TEXT("/save"), TEXT("{}"));
}

void USimClientComponent::CallTick(const FString& Event,
    const FString& ParamsJson)
{
    // Build the body string manually (fast & reflection-safe)
    FString Body = FString::Printf(
        TEXT("{\"event\":\"%s\",\"params\":%s}"),
        *Event.ReplaceCharWithEscapedChar(),   // escape quotes
        *ParamsJson);

    SendPOST(TEXT("/tick"), Body);
}

/* ---------------- internals ---------------- */

void USimClientComponent::SendPOST(const FString& Ep, const FString& Body)
{
    const FString URL = BaseURL + Ep;

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req =
        FHttpModule::Get().CreateRequest();
    Req->SetURL(URL);
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(Body);
    Req->OnProcessRequestComplete().BindUObject(
        this, &USimClientComponent::HandleResp);
    Req->ProcessRequest();
}

void USimClientComponent::HandleResp(
    FHttpRequestPtr Req, FHttpResponsePtr Resp, bool bOK)
{
    if (!bOK || !Resp.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("HTTP fail: %s"), *Req->GetURL());
        return;
    }

    const FString& JsonText = Resp->GetContentAsString();
    OnSimStateUpdated.Broadcast(JsonText);          // BP-friendly

    // optional C++ parse for your own use
    TSharedPtr<FJsonObject> J;
    if (FJsonSerializer::Deserialize(
        TJsonReaderFactory<>::Create(JsonText), J) && J.IsValid())
    {
        SimState = J;
    }
}
