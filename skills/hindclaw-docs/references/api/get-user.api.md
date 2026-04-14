

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Get User"}
>
</Heading>

<MethodEndpoint
  method={"get"}
  path={"/ext/hindclaw/users/{user_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Get User

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./get-user.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./get-user.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./get-user.StatusCodes.json")}
>
  
</StatusCodes>

      