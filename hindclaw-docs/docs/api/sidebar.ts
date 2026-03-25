import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebar: SidebarsConfig = {
  apisidebar: [
    {
      type: "doc",
      id: "api/hindclaw-api",
    },
    {
      type: "category",
      label: "Users",
      items: [
        {
          type: "doc",
          id: "api/list-users",
          label: "List Users",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/create-user",
          label: "Create User",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/get-user",
          label: "Get User",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/update-user",
          label: "Update User",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-user",
          label: "Delete User",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/list-user-channels",
          label: "List User Channels",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/add-user-channel",
          label: "Add User Channel",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/remove-user-channel",
          label: "Remove User Channel",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "Groups",
      items: [
        {
          type: "doc",
          id: "api/list-groups",
          label: "List Groups",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/create-group",
          label: "Create Group",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/get-group",
          label: "Get Group",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/update-group",
          label: "Update Group",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-group",
          label: "Delete Group",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/list-group-members",
          label: "List Group Members",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/add-group-member",
          label: "Add Group Member",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/remove-group-member",
          label: "Remove Group Member",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "API Keys",
      items: [
        {
          type: "doc",
          id: "api/list-api-keys",
          label: "List Api Keys",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/create-api-key",
          label: "Create Api Key",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/delete-api-key",
          label: "Delete Api Key",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "Policies",
      items: [
        {
          type: "doc",
          id: "api/list-policies",
          label: "List Policies",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/create-policy",
          label: "Create Policy",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/get-policy",
          label: "Get Policy Endpoint",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/update-policy",
          label: "Update Policy Endpoint",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-policy",
          label: "Delete Policy Endpoint",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/list-policy-attachments",
          label: "List Attachments",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/upsert-policy-attachment",
          label: "Upsert Attachment",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-policy-attachment",
          label: "Delete Attachment",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "Service Accounts",
      items: [
        {
          type: "doc",
          id: "api/list-service-accounts",
          label: "List Service Accounts",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/create-service-account",
          label: "Create Service Account",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/get-service-account",
          label: "Get Service Account Endpoint",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/update-service-account",
          label: "Update Service Account Endpoint",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-service-account",
          label: "Delete Service Account Endpoint",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/list-sa-keys",
          label: "List Sa Keys",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/create-sa-key",
          label: "Create Sa Key",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/delete-sa-key",
          label: "Delete Sa Key",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "Bank Policies",
      items: [
        {
          type: "doc",
          id: "api/get-bank-policy",
          label: "Get Bank Policy Endpoint",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/upsert-bank-policy",
          label: "Upsert Bank Policy Endpoint",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-bank-policy",
          label: "Delete Bank Policy Endpoint",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "Debug",
      items: [
        {
          type: "doc",
          id: "api/debug-resolve",
          label: "Debug Resolve",
          className: "api-method get",
        },
      ],
    },
  ],
};

export default sidebar.apisidebar;
