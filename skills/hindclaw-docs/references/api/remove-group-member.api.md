

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Remove Group Member"}
>
</Heading>

<MethodEndpoint
  method={"delete"}
  path={"/ext/hindclaw/groups/{group_id}/members/{user_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Remove Group Member

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./remove-group-member.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./remove-group-member.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./remove-group-member.StatusCodes.json")}
>
  
</StatusCodes>

      