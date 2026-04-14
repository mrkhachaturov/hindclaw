

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Add Group Member"}
>
</Heading>

<MethodEndpoint
  method={"post"}
  path={"/ext/hindclaw/groups/{group_id}/members"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Add Group Member

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./add-group-member.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./add-group-member.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./add-group-member.StatusCodes.json")}
>
  
</StatusCodes>

      