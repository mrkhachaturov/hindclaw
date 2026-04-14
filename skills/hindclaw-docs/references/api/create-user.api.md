

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Create User"}
>
</Heading>

<MethodEndpoint
  method={"post"}
  path={"/ext/hindclaw/users"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Create User

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  parameters={undefined}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./create-user.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./create-user.StatusCodes.json")}
>
  
</StatusCodes>

      