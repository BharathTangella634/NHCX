FROM httpd:alpine

# Enable more detailed access logs
RUN sed -i 's|LogFormat "%h %l %u %t \\"%r\\" %>s %b" common|LogFormat "%h %l %u %t \\"%r\\" %>s %b \\"%{Referer}i\\" \\"%{User-Agent}i\\" %T/%D" common|g' /usr/local/apache2/conf/httpd.conf

# Set error log level to debug for more details
RUN sed -i 's/LogLevel warn/LogLevel debug/g' /usr/local/apache2/conf/httpd.conf

# Change Apache default port to 8080
RUN sed -i 's/Listen 80/Listen 8080/g' /usr/local/apache2/conf/httpd.conf

COPY . /usr/local/apache2/htdocs/

EXPOSE 8080
