

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Delete Group"}
>
</Heading>

<MethodEndpoint
  method={"delete"}
  path={"/ext/hindclaw/groups/{group_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Delete Group

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./delete-group.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./delete-group.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./delete-group.StatusCodes.json")}
>
  
</StatusCodes>

      