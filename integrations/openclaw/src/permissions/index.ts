export type {
  UserProfile,
  GroupConfig,
  BankPermissions,
  PermissionOverride,
  ResolvedPermissions,
  DiscoveryResult,
  HindsightConfig,
} from './types.js';

export {
  scanConfigPath,
  buildChannelIndex,
  buildMembershipIndex,
  buildStrategyIndex,
  validateDiscovery,
} from './discovery.js';

export { resolvePermissions } from './resolver.js';
export { mergeGroups, overlayFields } from './merge.js';
