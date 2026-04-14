

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Update Group"}
>
</Heading>

<MethodEndpoint
  method={"put"}
  path={"/ext/hindclaw/groups/{group_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Update Group

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./update-group.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./update-group.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./update-group.StatusCodes.json")}
>
  
</StatusCodes>

      