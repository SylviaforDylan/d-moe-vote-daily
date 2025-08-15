// schedule.js
const { schedule } = require('@netlify/functions')

const handler = async (event, context) => {
  // 触发爬虫函数
  await fetch('/.netlify/functions/scrape')
  
  return {
    statusCode: 200,
  }
}

module.exports.handler = schedule('*/5 * * * *', handler)