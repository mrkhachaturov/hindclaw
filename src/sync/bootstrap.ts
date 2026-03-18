import type { HindsightClient } from '../client.js';
import type { BankConfig } from '../types.js';

const bootstrappedBanks = new Set<string>();

const CONFIG_FIELDS = [
  'retain_mission',
  'observations_mission',
  'reflect_mission',
  'retain_extraction_mode',
  'disposition_skepticism',
  'disposition_literalism',
  'disposition_empathy',
  'entity_labels',
] as const;

/**
 * Bootstrap a bank with config from file. If the bank config file doesn't
 * specify a retain_mission, use the default bankMission from plugin config
 * (I2-I3: automatic bank mission for unconfigured banks).
 */
export async function bootstrapBank(
  bankId: string,
  bankConfig: BankConfig,
  client: HindsightClient,
  defaultBankMission?: string,
): Promise<{ applied: boolean; error?: string }> {
  // Skip if already bootstrapped in this process
  if (bootstrappedBanks.has(bankId)) {
    return { applied: false };
  }

  try {
    // Check if bank already has config
    const serverConfig = await client.getBankConfig(bankId);
    const overrides = serverConfig.overrides ?? {};

    if (Object.keys(overrides).length > 0) {
      // Bank already configured — skip
      bootstrappedBanks.add(bankId);
      return { applied: false };
    }

    // Ensure bank exists in database before applying config/directives
    await client.ensureBank(bankId);

    // Bank is empty — apply config from file
    const configUpdates: Record<string, unknown> = {};

    for (const field of CONFIG_FIELDS) {
      const value = bankConfig[field as keyof BankConfig];
      if (value !== undefined) {
        configUpdates[field] = value;
      }
    }

    // I2-I3: If no retain_mission in bank config file, use default bankMission from plugin config
    if (!configUpdates.retain_mission && defaultBankMission) {
      configUpdates.retain_mission = defaultBankMission;
    }

    if (Object.keys(configUpdates).length > 0) {
      await client.updateBankConfig(bankId, configUpdates);
    }

    // Create directives
    for (const directive of bankConfig.directives ?? []) {
      await client.createDirective(bankId, { name: directive.name, content: directive.content });
    }

    bootstrappedBanks.add(bankId);
    return { applied: true };
  } catch (err) {
    return { applied: false, error: String(err) };
  }
}

// For testing — reset the tracking set
export function resetBootstrapState(): void {
  bootstrappedBanks.clear();
}
