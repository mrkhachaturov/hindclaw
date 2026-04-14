

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Create Api Key"}
>
</Heading>

<MethodEndpoint
  method={"post"}
  path={"/ext/hindclaw/users/{user_id}/api-keys"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Create Api Key

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./create-api-key.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./create-api-key.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./create-api-key.StatusCodes.json")}
>
  
</StatusCodes>

      