

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"List User Channels"}
>
</Heading>

<MethodEndpoint
  method={"get"}
  path={"/ext/hindclaw/users/{user_id}/channels"}
  context={"endpoint"}
>
  
</MethodEndpoint>

List User Channels

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./list-user-channels.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./list-user-channels.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./list-user-channels.StatusCodes.json")}
>
  
</StatusCodes>

      