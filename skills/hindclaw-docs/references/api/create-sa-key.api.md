

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Create Sa Key"}
>
</Heading>

<MethodEndpoint
  method={"post"}
  path={"/ext/hindclaw/service-accounts/{sa_id}/keys"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Create Sa Key

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./create-sa-key.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./create-sa-key.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./create-sa-key.StatusCodes.json")}
>
  
</StatusCodes>

      