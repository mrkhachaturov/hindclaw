

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Update User"}
>
</Heading>

<MethodEndpoint
  method={"put"}
  path={"/ext/hindclaw/users/{user_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Update User

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./update-user.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./update-user.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./update-user.StatusCodes.json")}
>
  
</StatusCodes>

      