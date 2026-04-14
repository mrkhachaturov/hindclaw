

<Heading
  as={"h1"}
  className={"openapi__heading"}
  children={"Delete Attachment"}
>
</Heading>

<MethodEndpoint
  method={"delete"}
  path={"/ext/hindclaw/policy-attachments/{policy_id}/{principal_type}/{principal_id}"}
  context={"endpoint"}
>
  
</MethodEndpoint>

Delete Attachment

<Heading
  id={"request"}
  as={"h2"}
  className={"openapi-tabs__heading"}
>
  <Translate id="theme.openapi.request.title">Request</Translate>
</Heading>

<ParamsDetails
  {...require("./delete-policy-attachment.ParamsDetails.json")}
>
  
</ParamsDetails>

<RequestSchema
  {...require("./delete-policy-attachment.RequestSchema.json")}
>
  
</RequestSchema>

<StatusCodes
  {...require("./delete-policy-attachment.StatusCodes.json")}
>
  
</StatusCodes>

      