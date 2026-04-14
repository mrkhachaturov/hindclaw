

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"List Sa Keys"}
>
</Heading>

<MethodEndpoint
  method={"get"}
  path={"/ext/hindclaw/service-accounts/{sa_id}/keys"}
  context={"endpoint"}
>
  
</MethodEndpoint>

List Sa Keys

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./list-sa-keys.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./list-sa-keys.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./list-sa-keys.StatusCodes.json")}
>
  
</StatusCodes>

      