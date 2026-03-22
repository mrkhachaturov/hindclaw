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
      ],
    },
    {
      type: "category",
      label: "Channels",
      items: [
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
      ],
    },
    {
      type: "category",
      label: "Members",
      items: [
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
      label: "Permissions",
      items: [
        {
          type: "doc",
          id: "api/list-bank-permissions",
          label: "List Bank Permissions",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/get-bank-permission",
          label: "Get Bank Permission",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/delete-bank-permission",
          label: "Delete Bank Permission",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/upsert-group-permission",
          label: "Upsert Group Bank Permission",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/upsert-user-permission",
          label: "Upsert User Bank Permission",
          className: "api-method put",
        },
      ],
    },
    {
      type: "category",
      label: "Strategies",
      items: [
        {
          type: "doc",
          id: "api/list-strategies",
          label: "List Strategies",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/upsert-strategy",
          label: "Upsert Strategy",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-strategy",
          label: "Delete Strategy",
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
