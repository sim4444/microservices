/* UPDATE THESE VALUES TO MATCH YOUR SETUP */

const PROCESSING_STATS_API_URL = "http://acit3855-lab9.eastus.cloudapp.azure.com/processing/stats"
const ANALYZER_API_URL = {
    stats: "http://acit3855-lab9.eastus.cloudapp.azure.com/analyzer/stats",
    order: "http://acit3855-lab9.eastus.cloudapp.azure.com/analyzer/events/order?index=0",
    rating: "http://acit3855-lab9.eastus.cloudapp.azure.com/analyzer/events/rating?index=0"
}

const CONSISTENCY_UPDATE_URL = "http://acit3855-lab9.eastus.cloudapp.azure.com/consistency_check/update";
const CONSISTENCY_CHECKS_URL = "http://acit3855-lab9.eastus.cloudapp.azure.com/consistency_check/checks";

// This function fetches and updates the general statistics
const makeReq = (url, cb) => {
    fetch(url)
        .then(res => res.json())
        .then((result) => {
            console.log("Received data: ", result)
            cb(result);
        }).catch((error) => {
            updateErrorMessages(error.message)
        })
}

const updateCodeDiv = (result, elemId) => document.getElementById(elemId).innerText = JSON.stringify(result)

const getLocaleDateStr = () => (new Date()).toUTCString()

const getStats = () => {
    document.getElementById("last-updated-value").innerText = getLocaleDateStr()
    
    makeReq(PROCESSING_STATS_API_URL, (result) => updateCodeDiv(result, "processing-stats"))
    makeReq(ANALYZER_API_URL.stats, (result) => updateCodeDiv(result, "analyzer-stats"))
    makeReq(ANALYZER_API_URL.order, (result) => updateCodeDiv(result, "event-order"))
    makeReq(ANALYZER_API_URL.rating, (result) => updateCodeDiv(result, "event-rating"))
}

const updateErrorMessages = (message) => {
    const id = Date.now()
    console.log("Creation", id)
    msg = document.createElement("div")
    msg.id = `error-${id}`
    msg.innerHTML = `<p>Something happened at ${getLocaleDateStr()}!</p><code>${message}</code>`
    document.getElementById("messages").style.display = "block"
    document.getElementById("messages").prepend(msg)
    setTimeout(() => {
        const elem = document.getElementById(`error-${id}`)
        if (elem) { elem.remove() }
    }, 7000)
}

const setup = () => {
    getStats()
    setInterval(() => getStats(), 4000) // Update every 4 seconds
}

document.addEventListener('DOMContentLoaded', setup)

function runConsistencyCheck() {
    const start = performance.now();

    fetch(CONSISTENCY_UPDATE_URL, {
        method: "POST"
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP error ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        console.log("Consistency update triggered:", data);
        fetch(CONSISTENCY_CHECKS_URL)
            .then(res => {
                if (!res.ok) throw new Error("No check results available yet.");
                return res.json();
            })
            .then(result => {
                document.getElementById("consistency-results").innerText = JSON.stringify(result, null, 2);
            })
    })
    .catch(err => {
        updateErrorMessages(err.message);
    });
}