const fs = require('fs');
const path = require('path');
const os = require('os');

const configPath = path.join(os.homedir(), '.clawdbot', 'clawdbot.json');
console.log(`Reading config from: ${configPath}`);

try {
    const raw = fs.readFileSync(configPath, 'utf8');
    const config = JSON.parse(raw);
    let changed = false;

    // 1. Update primary model
    if (config.agents?.defaults?.model?.primary) {
        const oldPrimary = config.agents.defaults.model.primary;
        const newPrimary = "openai/qwen2.5:1.5b";
        if (oldPrimary !== newPrimary) {
            console.log(`Replacing primary model: ${oldPrimary} -> ${newPrimary}`);
            config.agents.defaults.model.primary = newPrimary;
            changed = true;
        }
    }

    // 2. Update model definition in providers
    if (config.models?.providers?.openai?.models) {
        const models = config.models.providers.openai.models;
        const targetModel = models.find(m => m.id === "qwen2.5:7b");

        if (targetModel) {
            console.log(`Updating model definition: qwen2.5:7b -> qwen2.5:1.5b`);
            targetModel.id = "qwen2.5:1.5b";
            targetModel.name = "qwen2.5:1.5b";
            // 1.5b context window is smaller (32k usually for local run, but we keep 200k if supported or lower safely)
            // Actually Qwen2.5 supports 128k, but let's be safe with 32k for speed
            targetModel.contextWindow = 32768;
            targetModel.maxTokens = 4096;
            changed = true;
        }
    }

    if (changed) {
        fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
        console.log('✅ Config updated successfully to use 1.5b model.');
    } else {
        console.log('ℹ️ Config already set to use 1.5b model.');
    }

} catch (err) {
    console.error('❌ Error updating config:', err);
    process.exit(1);
}
