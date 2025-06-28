#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "SimClientComponent.generated.h"




/** Raw JSON text every time the sim replies. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
    FOnSimStateUpdated, const FString&, JsonText);

UCLASS(ClassGroup = (Custom), meta = (BlueprintSpawnableComponent))
class MYPROJECT_API USimClientComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    USimClientComponent();

    /** http://127.0.0.1:8000 by default */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sim")
    FString BaseURL = TEXT("http://127.0.0.1:8000");

    /** Blueprint-friendly broadcast (raw JSON string). */
    UPROPERTY(BlueprintAssignable, Category = "Sim")
    FOnSimStateUpdated OnSimStateUpdated;

    /** POST /load  (auto-called on BeginPlay) */
    UFUNCTION(BlueprintCallable, Category = "Sim") void CallLoad();

    /** POST /save  (auto-called on EndPlay) */
    UFUNCTION(BlueprintCallable, Category = "Sim") void CallSave();

    /**
     * POST /tick
     * @param EventName    e.g. "player_chat"
     * @param ParamsJson   already-serialized JSON for the "params" field
     */
    UFUNCTION(BlueprintCallable, Category = "Sim")
    void CallTick(const FString& EventName,
        const FString& ParamsJson);

private:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type) override;

    void SendPOST(const FString& Endpoint, const FString& Body);
    void HandleResp(FHttpRequestPtr, FHttpResponsePtr, bool bSuccess);

    /* Internal copy parsed with TSharedPtr – not exposed to UHT. */
    TSharedPtr<FJsonObject> SimState;
};
