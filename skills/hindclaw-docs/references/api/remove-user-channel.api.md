

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Remove User Channel"}
>
</Heading>

<MethodEndpoint
  method={"delete"}
  path={"/ext/hindclaw/users/{user_id}/channels/{provider}/{sender_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Remove User Channel

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./remove-user-channel.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./remove-user-channel.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./remove-user-channel.StatusCodes.json")}
>
  
</StatusCodes>

      