

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Delete User"}
>
</Heading>

<MethodEndpoint
  method={"delete"}
  path={"/ext/hindclaw/users/{user_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Delete User

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./delete-user.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./delete-user.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./delete-user.StatusCodes.json")}
>
  
</StatusCodes>

      