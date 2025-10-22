// Fixed version using Vercel Blob SDK approach for consistent filename handling
const TOKEN_PREFIX = "upstox_access_token"; // We'll search for files with this prefix

export default async function handler(req, res) {
  const timestamp = new Date().toISOString();

  // Add CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-API-Key, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    if (!process.env.BLOB_READ_WRITE_TOKEN) {
      return res.status(500).json({
        success: false,
        message: "Blob storage not configured"
      });
    }

    const blobToken = process.env.BLOB_READ_WRITE_TOKEN;
    const baseUrl = "https://blob.vercel-storage.com";

    if (req.method === "POST") {
      // Upstox API sends token data after generation
      const { access_token, expires_at, issued_at, client_id, user_id } = req.body;

      if (!access_token) {
        console.log(`[${timestamp}] Missing access_token in request body`);
        return res.status(400).json({ 
          success: false, 
          message: "access_token is required" 
        });
      }

      const tokenData = {
        access_token,
        expires_at,
        issued_at,
        client_id,
        user_id,
        stored_at: timestamp,
        expires_in_hours: expires_at ? Math.round((new Date(parseInt(expires_at)) - new Date()) / (1000 * 60 * 60)) : null
      };

      console.log(`[${timestamp}] Received token from Upstox API - cleaning up old tokens...`);

      try {
        // First, clean up any existing token files
        try {
          const listResponse = await fetch(`${baseUrl}?prefix=${TOKEN_PREFIX}`, {
            headers: { 'Authorization': `Bearer ${blobToken}` }
          });

          if (listResponse.ok) {
            const listData = await listResponse.json();
            if (listData.blobs && listData.blobs.length > 0) {
              console.log(`[${timestamp}] Found ${listData.blobs.length} existing token files to delete`);
              
              // Delete all existing token files
              const deletePromises = listData.blobs.map(async (blob) => {
                try {
                  const deleteResponse = await fetch(blob.url, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${blobToken}` }
                  });
                  console.log(`[${timestamp}] Deleted old token file: ${blob.pathname} (${deleteResponse.status})`);
                } catch (deleteError) {
                  console.warn(`[${timestamp}] Failed to delete ${blob.pathname}: ${deleteError.message}`);
                }
              });
              
              await Promise.all(deletePromises);
            }
          }
        } catch (cleanupError) {
          console.warn(`[${timestamp}] Cleanup error (continuing anyway): ${cleanupError.message}`);
        }

        // Store new token with current timestamp to make filename unique
        const uniqueFilename = `${TOKEN_PREFIX}_${Date.now()}.json`;
        const storeResponse = await fetch(`${baseUrl}/${uniqueFilename}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${blobToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(tokenData, null, 2)
        });

        if (!storeResponse.ok) {
          const errorText = await storeResponse.text();
          console.error(`[${timestamp}] Blob API response:`, storeResponse.status, errorText);
          throw new Error(`Blob API error: ${storeResponse.status} - ${errorText}`);
        }

        const result = await storeResponse.json();
        console.log(`[${timestamp}] New token stored successfully: ${result.url}`);

        return res.status(200).json({
          success: true,
          message: "Access token updated successfully",
          expires_in_hours: tokenData.expires_in_hours,
          stored_at: timestamp,
          client_id: tokenData.client_id
        });

      } catch (storeError) {
        console.error(`[${timestamp}] Failed to store token:`, storeError);
        return res.status(500).json({
          success: false,
          message: "Failed to update access token",
          error: storeError.message
        });
      }
    }

    if (req.method === "GET") {
      // Retrieve the most recent valid token
      try {
        console.log(`[${timestamp}] Retrieving current access token...`);

        // Get list of token files (should be only one after cleanup)
        const listResponse = await fetch(`${baseUrl}?prefix=${TOKEN_PREFIX}`, {
          headers: { 'Authorization': `Bearer ${blobToken}` }
        });

        if (!listResponse.ok) {
          throw new Error(`Failed to list token files: ${listResponse.status}`);
        }

        const listData = await listResponse.json();
        
        if (!listData.blobs || listData.blobs.length === 0) {
          console.log(`[${timestamp}] No token files found`);
          return res.status(404).json({
            success: false,
            message: "No access token found. Please generate a new token first."
          });
        }

        // Get the most recent token file (they should be sorted by creation time)
        const latestTokenFile = listData.blobs.sort((a, b) => 
          new Date(b.uploadedAt) - new Date(a.uploadedAt)
        )[0];

        console.log(`[${timestamp}] Fetching latest token file: ${latestTokenFile.pathname}`);

        const tokenResponse = await fetch(latestTokenFile.url);
        if (!tokenResponse.ok) {
          throw new Error(`Failed to fetch token content: ${tokenResponse.status}`);
        }

        const tokenDataString = await tokenResponse.text();
        const tokenData = JSON.parse(tokenDataString);

        const isExpired = tokenData.expires_at && new Date() > new Date(parseInt(tokenData.expires_at));
        const timeUntilExpiry = tokenData.expires_at 
          ? Math.round((new Date(parseInt(tokenData.expires_at)) - new Date()) / (1000 * 60 * 60)) 
          : null;

        if (isExpired) {
          console.log(`[${timestamp}] Token has expired`);
          return res.status(410).json({
            success: false,
            message: "Token has expired. Please generate a new token.",
            expired_at: new Date(parseInt(tokenData.expires_at)).toISOString()
          });
        }

        console.log(`[${timestamp}] Token retrieved successfully - expires in ${timeUntilExpiry}h`);

        return res.status(200).json({
          success: true,
          access_token: tokenData.access_token,
          expires_at: tokenData.expires_at,
          expires_in_hours: timeUntilExpiry,
          client_id: tokenData.client_id,
          user_id: tokenData.user_id,
          stored_at: tokenData.stored_at,
          is_valid: !isExpired
        });

      } catch (getError) {
        console.error(`[${timestamp}] Get error:`, getError);
        
        if (getError.message?.includes('404') || getError.message?.includes('not found')) {
          return res.status(404).json({
            success: false,
            message: "No access token found. Please generate a new token first."
          });
        }

        return res.status(500).json({
          success: false,
          message: "Failed to retrieve token",
          error: getError.message
        });
      }
    }

    return res.status(405).json({ 
      success: false, 
      message: `Method ${req.method} not allowed` 
    });

  } catch (error) {
    console.error(`[${timestamp}] Critical error:`, error);
    
    return res.status(500).json({
      success: false,
      message: "Internal server error",
      error: error.message
    });
  }
}