const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY;

const CONFIG_PATH = './ultra_fast_fluxdev.yaml';

// Read the configuration file as a string
const fs = require('fs');
const path = require('path');
const configFilePath = path.join(__dirname, CONFIG_PATH);
const configFileContent = fs.readFileSync(configFilePath, 'utf8');

// Convert the string to a base64 string
const base64Config = Buffer.from(configFileContent).toString('base64');

const test_input = {
    config: base64Config,
    dataset_url: "https://huggingface.co/nerijs/im-a-cool-lora/resolve/main/50_svportrait64.zip",
    job_id: Math.random().toString(36).substring(2, 15),
    webhook_url: "https://webhook.site/bd42310b-68b7-4d8f-a720-d0d15b1e3014",
};

// Save test_input.json
const testInputFilePath = path.join(__dirname, 'test_input.json');
fs.writeFileSync(testInputFilePath, JSON.stringify(test_input, null, 2), 'utf8');

async function main() {
    const url = "https://api.runpod.ai/v2/7wuje5a92wlzwd/runsync";

    const requestConfig = {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${RUNPOD_API_KEY}`
        },
        body: JSON.stringify({
            "input": test_input
        })
    };

    try {
        const response = await fetch(url, requestConfig);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log(data);
        console.log(data.output.results);
        return data;
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}

// Execute the function
main()
    .then(result => console.log('Success:', result))
    .catch(error => console.error('Error:', error));