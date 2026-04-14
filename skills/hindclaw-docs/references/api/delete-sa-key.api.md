

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Delete Sa Key"}
>
</Heading>

<MethodEndpoint
  method={"delete"}
  path={"/ext/hindclaw/service-accounts/{sa_id}/keys/{key_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Delete Sa Key

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./delete-sa-key.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./delete-sa-key.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./delete-sa-key.StatusCodes.json")}
>
  
</StatusCodes>

      