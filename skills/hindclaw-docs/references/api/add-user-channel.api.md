

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Add User Channel"}
>
</Heading>

<MethodEndpoint
  method={"post"}
  path={"/ext/hindclaw/users/{user_id}/channels"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Add User Channel

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./add-user-channel.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./add-user-channel.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./add-user-channel.StatusCodes.json")}
>
  
</StatusCodes>

      