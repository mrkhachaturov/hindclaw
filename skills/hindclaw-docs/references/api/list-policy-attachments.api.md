

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"List Attachments"}
>
</Heading>

<MethodEndpoint
  method={"get"}
  path={"/ext/hindclaw/policy-attachments"}
  context={"endpoint"}
>
  
</MethodEndpoint>

List Attachments

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./list-policy-attachments.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./list-policy-attachments.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./list-policy-attachments.StatusCodes.json")}
>
  
</StatusCodes>

      