import axios from 'axios'

const client = axios.create({
  baseURL: 'http://localhost:18432',
  timeout: 10000,
  paramsSerializer: { indexes: null },
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail
    if (detail) {
      return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
    }
    return Promise.reject(error)
  },
)

export default client
